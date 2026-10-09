from __future__ import annotations

import math
import os
import re
import struct
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

COMPLETE, MISSING, INVALID, UNKNOWN = 'GPS 完整', 'GPS 缺失', 'GPS 异常', '无法判断'
PHOTO, MOTION, VIDEO, OTHER = '普通照片（未识别动态）', '动态照片', '视频', '未知媒体'
SCOPES = ['全部媒体文件', '仅普通照片', '仅动态照片', '仅视频']
PHOTO_EXT = {'.jpg', '.jpeg', '.heic', '.heif', '.png', '.webp', '.tif', '.tiff', '.gif', '.bmp', '.avif', '.dng', '.cr2', '.cr3', '.nef', '.arw', '.raf', '.orf', '.rw2', '.raw', '.jxl', '.hif'}
VIDEO_EXT = {'.mp4', '.mov', '.m4v', '.3gp', '.3g2', '.avi', '.mkv', '.webm', '.mts', '.m2ts', '.mpeg', '.mpg', '.wmv', '.ts', '.vob', '.flv', '.insv'}
# A successfully parsed container is required before absence can be classified.
PHOTO_TYPES = {'JPEG', 'HEIC', 'HEIF', 'PNG', 'WEBP', 'TIFF', 'GIF', 'BMP', 'AVIF', 'DNG', 'CR2', 'CR3', 'NEF', 'ARW', 'RAF', 'ORF', 'RW2', 'JXL'}
VIDEO_TYPES = {'MP4', 'MOV', 'M4V', '3GP', '3G2', 'AVI', 'MKV', 'WEBM', 'M2TS', 'MTS', 'MPEG', 'WMV', 'ASF', 'FLV'}


def tag_items(meta, name):
    return [(k, v) for k, v in meta.items() if k.rsplit(':', 1)[-1].casefold() == name.casefold()]


def vals(meta, name):
    return [v for _, v in tag_items(meta, name)]


def first(meta, name, default=''):
    v = vals(meta, name)
    return v[0] if v else default


@dataclass
class GPS:
    status: str
    latitude: float | None = None
    longitude: float | None = None
    reason: str = ''
    evidence: str = ''


@dataclass
class Record:
    path: str
    kind: str
    file_type: str
    taken: str
    gps: GPS
    motion: str = '未发现可识别动态标记；不能排除标记被移除'
    evidence: str = ''
    identifier: str = ''
    marked: bool = False
    metadata: dict = field(default_factory=dict, repr=False)


@dataclass
class Asset:
    members: list[Record]
    kind: str
    motion: str = ''
    evidence: str = ''

    @property
    def gps_status(self):
        states = {m.gps.status for m in self.members}
        return next(s for s in (INVALID, UNKNOWN, MISSING, COMPLETE) if s in states)

    @property
    def problem(self):
        return self.gps_status != COMPLETE or (self.kind == MOTION and not self.motion.startswith('发现'))


@dataclass
class ScanResult:
    assets: list[Asset] = field(default_factory=list)
    records: list[Record] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    discovered: int = 0
    skipped: int = 0
    cancelled: bool = False
    scope: str = SCOPES[0]
    root: str = ''
    exiftool_version: str = ''


def number(value):
    if isinstance(value, bool):
        raise ValueError('布尔值不是坐标')
    n = float(value)
    if not math.isfinite(n):
        raise ValueError('坐标为 NaN/无穷值')
    return n


def gps_from_metadata(meta: dict, read_error='') -> GPS:
    errors = vals(meta, 'Error') + vals(meta, 'Warning')
    if read_error or errors:
        return GPS(UNKNOWN, reason=read_error or 'ExifTool 提示：' + '; '.join(map(str, errors)))
    ftype = str(first(meta, 'FileType')).upper()
    if ftype not in PHOTO_TYPES | VIDEO_TYPES:
        return GPS(UNKNOWN, reason=f'未支持或未确认的文件类型：{ftype or "未知"}')
    gps_tags = {k: v for k, v in meta.items() if any(s in k.lower() for s in ('gps', 'locationiso6709', 'locationinformation'))}
    evidence = '; '.join(f'{k}={v}' for k, v in gps_tags.items())[:12000]
    pairs = []
    problems = []
    # Group-specific coordinates; never combine latitude from one source with longitude from another.
    groups = {k.rsplit(':', 1)[0] if ':' in k else '' for k in meta if k.rsplit(':', 1)[-1] in ('GPSLatitude', 'GPSLongitude')}
    for g in sorted(groups):
        prefix = g + ':' if g else ''
        lat, lon = meta.get(prefix + 'GPSLatitude'), meta.get(prefix + 'GPSLongitude')
        if lat is None or lon is None:
            problems.append(f'{g}: 经纬度仅有一项')
            continue
        try:
            la, lo = number(lat), number(lon)
            for axis, refname, allowed in (('lat', 'GPSLatitudeRef', ('N', 'S')), ('lon', 'GPSLongitudeRef', ('E', 'W'))):
                ref = meta.get(prefix + refname)
                if ref is None and g.split(':')[0] == 'GPS':
                    refs = {str(v).upper() for k, v in tag_items(meta, refname) if k.split(':')[0] == 'GPS'}
                    if len(refs) == 1:
                        ref = next(iter(refs))
                    elif len(refs) > 1:
                        raise ValueError('多个 EXIF 半球标记冲突')
                # Native EXIF values are unsigned and require a hemisphere reference.
                if ref is None and (g.split(':')[0] == 'GPS' or g.startswith('EXIF')):
                    raise ValueError('EXIF 坐标缺少南北/东西半球标记')
                if ref is not None:
                    ref = str(ref).upper()
                    if ref not in allowed:
                        raise ValueError('半球标记不合法')
                    value = la if axis == 'lat' else lo
                    if value < 0 and ref == allowed[0]:
                        raise ValueError('坐标符号与半球冲突')
                    value = abs(value) * (-1 if ref == allowed[1] else 1)
                    if axis == 'lat':
                        la = value
                    else:
                        lo = value
            pairs.append((la, lo, g))
        except (ValueError, TypeError, OverflowError) as exc:
            problems.append(f'{g}: {exc}')
    # QuickTime GPSCoordinates is numeric under -n; ISO 6709 is accepted as a fallback.
    for key, value in tag_items(meta, 'GPSCoordinates') + tag_items(meta, 'GPSPosition') + tag_items(meta, 'LocationISO6709'):
        try:
            if isinstance(value, (list, tuple)):
                parts = value
            else:
                s = str(value).strip()
                iso = re.fullmatch(r'([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)(?:[+-]\d+(?:\.\d+)?)?/?', s)
                parts = iso.groups() if iso else re.split(r'[ ,]+', s)
            if len(parts) < 2:
                raise ValueError('坐标项数不足')
            pairs.append((number(parts[0]), number(parts[1]), key))
        except (ValueError, TypeError, OverflowError) as exc:
            problems.append(f'{key}: 无法解析坐标（{exc}）')
    if problems:
        return GPS(INVALID, reason='; '.join(problems), evidence=evidence)
    if not pairs:
        if gps_tags:
            return GPS(UNKNOWN, reason='存在 GPS/位置相关字段，但未提取到可验证经纬度', evidence=evidence)
        return GPS(MISSING, reason='元数据成功读取；受支持字段中未发现经纬度（不等于证明传输丢失）')
    for la, lo, source in pairs:
        if abs(la) > 90 or abs(lo) > 180:
            return GPS(INVALID, reason=f'{source}: 经纬度超出范围', evidence=evidence)
        if la == 0 and lo == 0:
            return GPS(INVALID, latitude=la, longitude=lo, reason='经纬度均为 0，可能是占位值；也可能是真实位置，请人工核实', evidence=evidence)
    la, lo, source = pairs[0]
    if any(abs(a - la) > 0.0001 or min(abs(b - lo), abs(abs(b-lo)-360)) > 0.0001 for a, b, _ in pairs[1:]):
        return GPS(INVALID, reason='不同元数据来源的经纬度不一致（阈值 0.0001°）', evidence=evidence)
    return GPS(COMPLETE, la, lo, '经纬度数值及范围通过检查；不验证实际拍摄地点', evidence)


def sniff(path: Path):
    with path.open('rb') as f:
        h = f.read(64)
    if h.startswith((b'\xff\xd8\xff', b'\x89PNG\r\n\x1a\n', b'GIF87a', b'GIF89a', b'II*\x00', b'MM\x00*', b'BM')):
        return PHOTO
    if h[4:8] == b'ftyp':
        return PHOTO if any(x in h[8:] for x in (b'heic', b'heix', b'hevc', b'hevx', b'mif1', b'avif', b'avis')) else VIDEO
    if h.startswith(b'RIFF'):
        return PHOTO if h[8:12] == b'WEBP' else VIDEO if h[8:12] == b'AVI ' else ''
    if h.startswith(b'\x1aE\xdf\xa3') or h[4:8] in (b'moov', b'wide', b'mdat'):
        return VIDEO
    return ''


def discover(root: Path, cancel: threading.Event, progress, notices):
    paths, skipped = [], 0
    def err(exc):
        notices.append(f'目录无法读取：{exc}')
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=err):
        if cancel.is_set():
            break
        kept = []
        for d in sorted(dirs):
            p = Path(directory) / d
            if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
                notices.append(f'跳过目录链接：{p}')
            else:
                kept.append(d)
        dirs[:] = kept
        for name in sorted(files):
            if cancel.is_set():
                break
            p = Path(directory) / name
            if p.is_symlink() or not p.is_file():
                notices.append(f'跳过链接或非常规文件：{p}')
                continue
            known = p.suffix.lower() in PHOTO_EXT | VIDEO_EXT
            try:
                match = known or bool(sniff(p))
            except OSError as exc:
                match = known
                notices.append(f'无法探测文件：{p}: {exc}')
            if match:
                paths.append(p)
            else:
                skipped += 1
            if (len(paths) + skipped) % 100 == 0:
                progress('发现文件', len(paths), 0)
    return paths, skipped


def validate_mp4_region(path: Path, start: int, length: int):
    """Bounded top-level ISO BMFF structure probe, not a video decoder."""
    if start < 0 or length < 24:
        return False, '视频偏移或长度不合理'
    try:
        size = path.stat().st_size
        if start + length > size:
            return False, '视频范围超出文件长度'
        seen = set()
        with path.open('rb') as f:
            pos, end = start, start + length
            for _ in range(10000):
                if pos == end:
                    break
                if pos + 8 > end:
                    return False, '视频 box 头截断'
                f.seek(pos)
                n, kind = struct.unpack('>I4s', f.read(8))
                header = 8
                if n == 1:
                    raw = f.read(8)
                    if len(raw) != 8:
                        return False, '扩展 box 长度截断'
                    n, header = struct.unpack('>Q', raw)[0], 16
                elif n == 0:
                    n = end - pos
                if n < header or pos + n > end:
                    return False, '视频 box 长度越界'
                if pos == start and kind != b'ftyp':
                    return False, '声明的视频起点不是 ftyp'
                seen.add(kind)
                pos += n
            else:
                return False, '视频 box 数量过多'
        ok = {b'ftyp', b'moov', b'mdat'} <= seen
        return ok, '发现 ftyp/moov/mdat，长度边界通过；未解码验证播放' if ok else '未找到完整 ftyp/moov/mdat 结构'
    except (OSError, struct.error) as exc:
        return False, f'读取动态部分失败：{exc}'


def container_items(value):
    """Extract ordered directory items from ExifTool -struct JSON."""
    if isinstance(value, list):
        for child in value:
            yield from container_items(child)
    elif isinstance(value, dict):
        short = {k.rsplit(':', 1)[-1]: v for k, v in value.items()}
        if 'Semantic' in short and ('Length' in short or short['Semantic'] == 'Primary'):
            yield short
        else:
            for child in value.values():
                yield from container_items(child)


def motion_info(path, meta):
    marked = any(str(v) == '1' for n in ('MotionPhoto', 'MicroVideo') for v in vals(meta, n))
    hints = []
    for k, v in meta.items():
        if any(s in k.lower() for s in ('motionphoto', 'microvideo', 'livephoto', 'microvideooffset')):
            hints.append(f'{k}={v}')
    for k, v in tag_items(meta, 'EmbeddedVideoType') + tag_items(meta, 'EmbeddedVideoFile'):
        hints.append(f'{k}={v}')
    regions = []
    try:
        size = path.stat().st_size
        # New container layout takes priority. Calculate from end, including following items/padding.
        items = [i for value in (vals(meta, 'Directory') + vals(meta, 'ContainerDirectory')) for i in container_items(value)]
        remaining = 0
        for item in reversed(items):
            length = int(item.get('Length', 0))
            padding = int(item.get('Padding', 0))
            if length < 0 or padding < 0:
                raise ValueError('负数容器长度')
            if item.get('Semantic') == 'MotionPhoto':
                regions.append((size - remaining - length - padding, length, 'XMP 容器目录'))
                marked = True
            remaining += length + padding
        if not regions:
            for value in vals(meta, 'MicroVideoOffset'):
                offset = int(value)
                if offset > 0:
                    regions.append((size - offset, offset, '旧版 MicroVideoOffset'))
        for start, length, source in regions:
            ok, reason = validate_mp4_region(path, start, length)
            hints.append(f'{source}: start={start}, length={length}; {reason}')
            if ok:
                return True, '发现内嵌动态部分（结构检查，未验证播放）', '; '.join(hints)
        if regions:
            return True, '动态部分异常或无法确认（声明与结构不匹配）', '; '.join(hints)
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        hints.append(f'动态范围解析失败：{exc}')
    disabled = vals(meta, 'MotionPhoto')
    if disabled and all(str(v) == '0' for v in disabled) and not regions and not vals(meta, 'EmbeddedVideoFile') and not vals(meta, 'MotionPhotoVideo'):
        return False, 'MotionPhoto 标记为 0；未验证存在动态部分', '; '.join(hints)
    if hints or marked:
        return True, '动态部分无法确认（有标记，但没有通过位置及结构验证）', '; '.join(hints)
    return False, '未发现可识别动态标记；不能排除标记被移除', ''


def make_record(path: Path, meta: dict, read_error=''):
    ft = str(first(meta, 'FileType')).upper()
    kind = PHOTO if ft in PHOTO_TYPES else VIDEO if ft in VIDEO_TYPES else PHOTO if path.suffix.lower() in PHOTO_EXT else VIDEO if path.suffix.lower() in VIDEO_EXT else OTHER
    gps = gps_from_metadata(meta, read_error)
    taken = ''
    for name in ('DateTimeOriginal', 'CreationDate', 'CreateDate', 'MediaCreateDate'):
        v = first(meta, name)
        if v:
            taken = f'{v} [{name}]'
            break
    record = Record(str(path), kind, ft or path.suffix, taken, gps, metadata=meta)
    # Content identifiers only; burst identifiers and file names are deliberately not sufficient.
    ids = {str(v).strip() for name in ('ContentIdentifier', 'MediaGroupUUID') for v in vals(meta, name) if str(v).strip()}
    record.identifier = next(iter(ids)) if len(ids) == 1 else ''
    if len(ids) > 1:
        record.evidence += '多个内容标识冲突，不自动配对；'
    if kind == PHOTO:
        marked, motion, evidence = motion_info(path, meta)
        record.marked, record.motion = marked, motion
        record.evidence += evidence
        if marked:
            record.kind = MOTION
    else:
        record.motion = '不适用'
    return record


def group_records(records: list[Record], scope: str, cancel=None):
    groups = {}
    for r in records:
        if r.identifier:
            groups.setdefault(r.identifier, []).append(r)
    paired = {}
    consumed = set()
    for ident, members in groups.items():
        photos = [r for r in members if r.kind in (PHOTO, MOTION)]
        videos = [r for r in members if r.kind == VIDEO]
        if len(photos) == len(videos) == 1:
            p, v = photos[0], videos[0]
            valid_type = v.file_type in VIDEO_TYPES and v.gps.status != UNKNOWN
            motion = '发现配对动态部分（未验证播放）' if valid_type else '配对动态部分无法确认（读取失败或格式未确认）'
            paired[p.path] = Asset([p, v], MOTION, motion, f'唯一相同内容标识 {ident}；两文件分别检查 GPS；{p.evidence}')
            consumed.add(v.path)
        else:
            for r in members:
                r.evidence += '; 内容标识不唯一或缺少配对成员，不自动合并'
    stems = {}
    for r in records:
        stems.setdefault((str(Path(r.path).parent), Path(r.path).stem.casefold()), []).append(r)
    assets = []
    for r in records:
        if r.path in consumed:
            continue
        asset = paired.get(r.path) or Asset([r], r.kind, r.motion, r.evidence)
        same = stems[(str(Path(r.path).parent), Path(r.path).stem.casefold())]
        if r.path not in paired and len(same) > 1 and any(s.kind == VIDEO for s in same) and any(s.kind in (PHOTO, MOTION) for s in same):
            asset.evidence += '; 存在同名照片/视频，仅为配对候选；证据不足，保留独立计数'
            if asset.kind in (PHOTO, MOTION):
                asset.kind = MOTION
                asset.motion = '疑似配对动态照片，无法确认'
        if scope == SCOPES[0] or (scope == SCOPES[1] and asset.kind == PHOTO) or (scope == SCOPES[2] and asset.kind == MOTION) or (scope == SCOPES[3] and asset.kind == VIDEO):
            assets.append(asset)
    return assets


def scan(root, reader, cancel=None, progress: Callable = lambda *a: None, scope=SCOPES[0]):
    cancel = cancel or threading.Event()
    root = Path(root).absolute()
    if not root.is_dir():
        raise ValueError('扫描目录不存在或不可访问')
    result = ScanResult(scope=scope, root=str(root), exiftool_version=getattr(reader, 'version', ''))
    paths, result.skipped = discover(root, cancel, progress, result.notices)
    result.discovered = len(paths)
    progress('读取元数据', 0, len(paths))
    for start in range(0, len(paths), 16):
        if cancel.is_set():
            break
        batch = paths[start:start + 16]
        responses = reader.read(batch, cancel)
        for path in batch:
            if cancel.is_set():
                break
            meta, error = responses.get(str(path), ({}, 'ExifTool 未返回此文件，无法判断'))
            try:
                r = make_record(path, meta, error)
            except Exception as exc:
                r = Record(str(path), OTHER, path.suffix, '', GPS(UNKNOWN, reason=f'元数据解析失败：{exc}'))
            result.records.append(r)
        progress('读取元数据', len(result.records), len(paths))
    result.cancelled = cancel.is_set()
    progress('整理配对', len(result.records), len(paths))
    result.assets = group_records(result.records, scope)
    from .capture_time import asset_time_key
    result.assets.sort(key=asset_time_key)
    if result.cancelled:
        result.notices.append('扫描已取消；报告仅包括已完成读取的文件，配对和统计均不完整。')
    return result
