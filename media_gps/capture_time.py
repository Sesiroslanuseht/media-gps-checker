"""Capture-time parsing. Never uses filesystem creation/modification dates."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re

from .core import tag_items, vals


@dataclass(frozen=True)
class CaptureTime:
    local: datetime | None
    utc: datetime | None
    source: str
    note: str
    raw: str = ''


def fixed_timezone(offset='+08:00'):
    m = re.fullmatch(r'([+-])(\d{2}):(\d{2})', offset)
    if not m or int(m[2]) > 14 or int(m[3]) > 59 or (int(m[2]) == 14 and int(m[3]) != 0):
        raise ValueError('时区应为 +08:00 这样的格式，范围 -14:00 至 +14:00')
    minutes = (int(m[2]) * 60 + int(m[3])) * (1 if m[1] == '+' else -1)
    return timezone(timedelta(minutes=minutes))


def parse_datetime(raw):
    text = str(raw).strip()
    # ExifTool date strings: YYYY:mm:dd HH:MM:SS[.fraction][+08:00].
    text = re.sub(r'^(\d{4}):(\d{2}):(\d{2})', r'\1-\2-\3', text)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?', text):
        raise ValueError('缺少完整年月日时分秒或时间格式不支持')
    value = datetime.fromisoformat(text.replace('Z', '+00:00'))
    if value.tzinfo and abs(value.utcoffset()) > timedelta(hours=14):
        raise ValueError('时区偏移超出范围')
    if value.year < 1900:
        raise ValueError('拍摄年份早于 1900，可能是未初始化的时间')
    return value


def capture_time(record, offset='+08:00'):
    zone = fixed_timezone(offset)
    meta = record.metadata
    names = ('SubSecDateTimeOriginal', 'DateTimeOriginal', 'CreationDate', 'SubSecCreateDate', 'CreateDate', 'MediaCreateDate')
    for name in names:
        items = [(k, v) for k, v in tag_items(meta, name) if str(v).strip()]
        if not items:
            continue
        candidates = []
        try:
            for key, raw in items:
                dt = parse_datetime(raw)
                note = ''
                if dt.tzinfo is None:
                    # Only use EXIF offset/subsecond companions for EXIF-style times.
                    refname = 'OffsetTimeOriginal' if name == 'DateTimeOriginal' else 'OffsetTimeDigitized' if name == 'CreateDate' else ''
                    refs = {str(v).strip() for v in vals(meta, refname)} if refname and key.split(':')[0] in ('ExifIFD', 'EXIF') else set()
                    if len(refs) > 1:
                        raise ValueError('拍摄时间的时区字段冲突')
                    if refs:
                        dt = dt.replace(tzinfo=fixed_timezone(refs.pop()))
                        note = '使用 EXIF 时区字段'
                    elif key.split(':')[0] in ('QuickTime', 'Track1', 'Track2', 'Media') and name in ('CreateDate', 'MediaCreateDate'):
                        dt = dt.replace(tzinfo=timezone.utc)
                        note = '视频整数时间按 QuickTime 标准视为 UTC；部分设备可能不遵循标准'
                    else:
                        dt = dt.replace(tzinfo=zone)
                        note = f'元数据未带时区，按行程时区 UTC{offset} 解释'
                else:
                    note = '使用元数据自带时区'
                subname = 'SubSecTimeOriginal' if name == 'DateTimeOriginal' else 'SubSecTimeDigitized' if name == 'CreateDate' else ''
                if subname and not re.search(r':\d{2}\.\d+', str(raw)):
                    subs = {str(v).strip() for v in vals(meta, subname)}
                    if len(subs) > 1:
                        raise ValueError('拍摄时间的亚秒字段冲突')
                    if subs:
                        sub = subs.pop()
                        if not sub.isdigit():
                            raise ValueError('亚秒字段不是数字')
                        dt = dt.replace(microsecond=int((sub + '000000')[:6]))
                candidates.append((dt.astimezone(timezone.utc), key, str(raw), note))
            first = candidates[0]
            if any(item[0] != first[0] for item in candidates[1:]):
                raise ValueError('同级拍摄时间字段相互冲突')
            utc, key, raw, note = first
            if name in ('CreateDate', 'MediaCreateDate', 'SubSecCreateDate'):
                note += '；未读到更优先的原始拍摄时间，使用媒体创建元数据'
            return CaptureTime(utc.astimezone(zone), utc, key, note, raw)
        except (ValueError, TypeError, OverflowError) as exc:
            return CaptureTime(None, None, name, f'拍摄时间无法确定：{exc}', str(items[0][1]))
    # Supports records restored from an older report/test. No filesystem time fallback.
    if record.taken:
        raw = re.sub(r'\s+\[[^\]]+\]$', '', record.taken)
        try:
            dt = parse_datetime(raw)
            note = '使用记录中的拍摄时间'
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=zone)
                note += f'；无时区，按 UTC{offset} 解释'
            return CaptureTime(dt.astimezone(zone), dt.astimezone(timezone.utc), '已记录拍摄时间', note, raw)
        except (ValueError, TypeError, OverflowError) as exc:
            return CaptureTime(None, None, '', f'拍摄时间无法确定：{exc}', raw)
    return CaptureTime(None, None, '', '没有可用拍摄时间；不使用电脑文件时间')


def asset_time_key(asset, offset='+08:00'):
    t = capture_time(asset.members[0], offset)
    return (t.utc is None, t.utc or datetime.max.replace(tzinfo=timezone.utc), asset.members[0].path.casefold(), asset.members[0].path)
