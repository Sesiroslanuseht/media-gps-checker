"""Real ExifTool integration; fixtures are created only inside temporary directories."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

from media_gps.core import *
from media_gps.exiftool import ExifTool
from media_gps.export import export_xlsx

EXE = os.environ.get('EXIFTOOL_TEST_PATH') or shutil.which('exiftool')


@unittest.skipUnless(EXE, '设置 EXIFTOOL_TEST_PATH 才执行真实 ExifTool 测试')
class RealExifToolTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / '小米 相册 #中文'
        self.root.mkdir()
        self.with_gps = self.root / '有位置.jpg'
        self.no_gps = self.root / '无位置.PNG'
        Image.new('RGB', (32, 32), 'blue').save(self.with_gps)
        Image.new('RGB', (32, 32), 'red').save(self.no_gps)
        self.write_tags(self.with_gps, '-GPSLatitude=30.25', '-GPSLatitudeRef=N', '-GPSLongitude=120.5', '-GPSLongitudeRef=E', '-DateTimeOriginal=2026:10:09 12:00:00')
        self.reader = ExifTool(EXE)
        self.reader.check()

    def write_tags(self, path, *tags):
        # Fixture setup only. Production scanner never calls this function or supplies write flags.
        args = '\n'.join([*tags, '-overwrite_original', str(path)]) + '\n'
        subprocess.run([EXE, '-config', '', '-charset', 'filename=UTF8', '-@', '-'], input=args.encode(), check=True, capture_output=True)

    def test_real_jpeg_png_corruption_unicode_readonly(self):
        bad = self.root / '损坏.heic'
        bad.write_bytes(b'broken\x00\x01\x02')
        disguised = self.root / '无扩展名'
        shutil.copyfile(self.with_gps, disguised)
        before = {p.name: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) for p in self.root.iterdir()}
        result = scan(self.root, self.reader)
        by_name = {Path(r.path).name: r for r in result.records}
        self.assertEqual(by_name[self.with_gps.name].gps.status, COMPLETE, str(by_name[self.with_gps.name].gps))
        self.assertEqual(by_name[self.no_gps.name].gps.status, MISSING, str(by_name[self.no_gps.name].gps))
        self.assertEqual(by_name[bad.name].gps.status, UNKNOWN)
        self.assertEqual(by_name[disguised.name].gps.status, COMPLETE)
        export_xlsx(result, Path(self.tmp.name) / 'report.xlsx')
        after = {p.name: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) for p in self.root.iterdir()}
        self.assertEqual(before, after)

    @unittest.skipUnless(shutil.which('ffmpeg'), '需要 FFmpeg 生成真实视频测试素材')
    def test_real_video_embedded_motion_and_stale_marker(self):
        video = self.root / '视频.MP4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=32x32:d=0.2', '-c:v', 'mpeg4', str(video)], check=True, capture_output=True)
        self.write_tags(video, '-Keys:GPSCoordinates=+30.2500+120.5000+12.0/')
        dynamic = self.root / '动态照片.jpg'
        shutil.copyfile(self.with_gps, dynamic)
        self.write_tags(dynamic, '-XMP-GCamera:MicroVideo=1', f'-XMP-GCamera:MicroVideoOffset={video.stat().st_size}')
        with dynamic.open('ab') as f:
            f.write(video.read_bytes())
        stale = self.root / '残留标记.jpg'
        shutil.copyfile(self.with_gps, stale)
        self.write_tags(stale, '-XMP-GCamera:MotionPhoto=1')
        result = scan(self.root, self.reader)
        by_name = {Path(r.path).name: r for r in result.records}
        self.assertEqual(by_name[video.name].gps.status, COMPLETE, str(by_name[video.name].gps))
        self.assertTrue(by_name[dynamic.name].motion.startswith('发现'), by_name[dynamic.name].evidence)
        self.assertIn('无法确认', by_name[stale.name].motion)

    def test_real_new_container_xmp(self):
        from test_core import mp4
        data = mp4()
        path = self.root / '新容器.jpg'
        shutil.copyfile(self.with_gps, path)
        xmp = f'''<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description xmlns:GCamera="http://ns.google.com/photos/1.0/camera/" xmlns:Container="http://ns.google.com/photos/1.0/container/" xmlns:Item="http://ns.google.com/photos/1.0/container/item/" GCamera:MotionPhoto="1"><Container:Directory><rdf:Seq><rdf:li rdf:parseType="Resource"><Container:Item Item:Mime="image/jpeg" Item:Semantic="Primary" Item:Padding="0"/></rdf:li><rdf:li rdf:parseType="Resource"><Container:Item Item:Mime="video/mp4" Item:Semantic="MotionPhoto" Item:Length="{len(data)}" Item:Padding="0"/></rdf:li></rdf:Seq></Container:Directory></rdf:Description></rdf:RDF></x:xmpmeta>'''.encode()
        packet = b'http://ns.adobe.com/xap/1.0/\0' + xmp
        original = path.read_bytes()
        path.write_bytes(original[:2] + b'\xff\xe1' + (len(packet)+2).to_bytes(2, 'big') + packet + original[2:] + data)
        response = self.reader.read([path], threading.Event())[str(path)]
        r = make_record(path, *response)
        self.assertTrue(r.motion.startswith('发现'), str(response) + '\n' + r.evidence)


class ProcessCancellationTests(unittest.TestCase):
    @unittest.skipIf(os.name == 'nt', 'POSIX 慢进程夹具；Windows 取消待实机验证')
    def test_real_process_cancel_and_timeout(self):
        import time
        from media_gps.exiftool import Cancelled
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / 'slow_exiftool'
            executable.write_text('#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n')
            executable.chmod(0o755)
            reader = ExifTool(str(executable), timeout=0.2)
            begin = time.monotonic()
            with self.assertRaises(TimeoutError):
                reader._run([], None, threading.Event())
            self.assertLess(time.monotonic() - begin, 3)
            event = threading.Event()
            timer = threading.Timer(0.2, event.set)
            timer.start()
            with self.assertRaises(Cancelled):
                reader._run([], None, event, 5)
            timer.join()
