#!/usr/bin/env python3
"""本轮离线重构的可复现对照检查，仅使用内存和临时文件。"""

import argparse
import contextlib
from dataclasses import asdict
import io
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import warnings


def main():
    warnings.filterwarnings('ignore', category=DeprecationWarning)
    parser = argparse.ArgumentParser(description='比较重构前后的离线数据行为，不连接 ROS 或硬件。')
    parser.add_argument('--reference', default='HEAD', help='重构前的 Git 引用，默认 HEAD')
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    reference = subprocess.check_output(['git', 'rev-parse', arguments.reference], cwd=root).decode('ascii').strip()
    paths = {
        'snapshot': 'src/ylhb_mobile_bridge/ylhb_mobile_bridge/map_snapshot.py',
        'position': 'scripts/position_error_evaluator.py',
        'relocalization': 'scripts/relocalization_evaluator.py',
    }
    modules = {}
    for label, relative in paths.items():
        old_source = subprocess.check_output(['git', 'show', reference + ':' + relative], cwd=root).decode('utf-8')
        new_source = (root / relative).read_text(encoding='utf-8')
        for version, source in [('old', old_source), ('new', new_source)]:
            name = label + '_' + version
            module = ModuleType(name)
            sys.modules[name] = module
            exec(compile(source, relative, 'exec'), module.__dict__)
            modules[name] = module

    rng = random.Random(20261015)
    counts = {'map_snapshots': 0, 'position_batches': 0, 'position_csv_inputs': 0, 'relocalization_batches': 0, 'relocalization_csv_inputs': 0, 'invalid_map_inputs': 0}

    def normalized(value):
        if hasattr(value, '__dataclass_fields__'):
            value = asdict(value)
        return json.dumps(value, sort_keys=True, allow_nan=True)

    def outcome(function, *args):
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                result = function(*args)
            if isinstance(result, list):
                result = [asdict(item) for item in result]
            return ('result', normalized(result))
        except Exception as exc:
            return ('exception', type(exc).__name__)

    for index in range(150):
        width, height = rng.randint(1, 64), rng.randint(1, 64)
        grid = SimpleNamespace(
            header=SimpleNamespace(frame_id='map', stamp=SimpleNamespace(sec=index, nanosec=500000000)),
            info=SimpleNamespace(width=width, height=height, resolution=0.05, origin=SimpleNamespace(
                position=SimpleNamespace(x=1.0, y=-2.0, z=0.0),
                orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0))),
            data=[rng.choice([-1, 0, 25, 26, 64, 65, 100]) for _ in range(width * height)])
        downsample = rng.choice([-2, 0, 1, 2, 16, 99])
        max_size = rng.choice([-1, 0, 1, 3, 8, 64, 1024])
        old = modules['snapshot_old'].occupancy_grid_to_png_snapshot(grid, downsample, max_size)
        new = modules['snapshot_new'].occupancy_grid_to_png_snapshot(grid, downsample, max_size)
        assert old == new, ('snapshot', index)
        counts['map_snapshots'] += 1

    for values in [[], [0], [0] * 3]:
        grid.info.width, grid.info.height, grid.data = 2, 2, values
        assert outcome(modules['snapshot_old'].occupancy_grid_to_png_snapshot, grid) == outcome(modules['snapshot_new'].occupancy_grid_to_png_snapshot, grid)
        counts['invalid_map_inputs'] += 1

    for index in range(120):
        values = [(
            float(sample), rng.uniform(-10, 10), rng.uniform(-10, 10),
            rng.uniform(-10, 10), rng.uniform(-10, 10),
            rng.choice([None, rng.uniform(-2, 2)]), rng.choice([None, rng.uniform(-2, 2)]),
        ) for sample in range(rng.randint(0, 30))]
        for function in ['compute_metrics', 'compute_vertical_metrics']:
            results = []
            for version in ['old', 'new']:
                module = modules['position_' + version]
                results.append(normalized(getattr(module, function)([module.PositionSample(*value) for value in values])))
            assert results[0] == results[1], ('position', index, function)
        counts['position_batches'] += 1

    for index in range(120):
        values = [(float(sample), sample, rng.choice(['RECOVERED', 'FAILED', 'MANUAL_REQUIRED', 'UNKNOWN']), rng.choice([None, 0.0, rng.uniform(0, 50)]), rng.choice([None, '', 'operator', 'lost'])) for sample in range(rng.randint(0, 40))]
        results = []
        for version in ['old', 'new']:
            module = modules['relocalization_' + version]
            results.append(normalized(module.compute_metrics([module.RelocalizationEvent(*value) for value in values])))
        assert results[0] == results[1], ('relocalization', index)
        counts['relocalization_batches'] += 1

    with tempfile.TemporaryDirectory() as directory:
        position_header = 'timestamp,estimated_x,estimated_y,ground_truth_x,ground_truth_y,estimated_z,ground_truth_z\n'
        position_inputs = [
            position_header + '1,1,2,1,2,0.25,0.20\n',
            position_header + '1,1,2,1,2, ,\n',
            position_header + '1,1,2,1,2,bad,0.2\n',
            position_header + 'bad,1,2,1,2,,\n',
            position_header + 'bad,1\n',
            position_header + '1,1,2,1,2,bad\n',
            position_header + 'bad,1,2,1,2,bad,bad\n',
            'timestamp,estimated_x,estimated_y,ground_truth_x,ground_truth_y\n1,1,2,1,2\n',
            position_header + '1,1,2,1,2,nan,inf\n',
            '',
        ]
        for index, content in enumerate(position_inputs):
            path = Path(directory) / f'position_{index}.csv'
            path.write_text(content, encoding='utf-8')
            assert outcome(modules['position_old'].read_csv, str(path)) == outcome(modules['position_new'].read_csv, str(path)), ('position_csv', index)
            counts['position_csv_inputs'] += 1
        relocation_header = 'timestamp,attempt_id,outcome,time_to_recovery,failure_reason\n'
        for index, content in enumerate([
            relocation_header + '1,1,RECOVERED,2.5,None\n',
            relocation_header + '1,1,MANUAL_REQUIRED,,operator\n',
            relocation_header + '1,1,FAILED,None,None\n',
            relocation_header + '1,1,UNKNOWN,,\n',
            relocation_header + '1,invalid,FAILED,,\n',
            '',
        ]):
            path = Path(directory) / f'relocation_{index}.csv'
            path.write_text(content, encoding='utf-8')
            assert outcome(modules['relocalization_old'].read_csv, str(path)) == outcome(modules['relocalization_new'].read_csv, str(path)), ('relocalization_csv', index)
            counts['relocalization_csv_inputs'] += 1

    print(json.dumps({'status': 'PASS', 'scope': 'LOCAL_ONLY', 'seed': 20261015, 'reference': reference, 'comparison': '重构前 Git 源码与当前工作树', 'checks': counts, 'total_cases': sum(counts.values()), 'limitations': ['未运行 ROS 或硬件', '异常比较只检查类型，警告文字不是契约', '固定种子的随机对照不是穷尽证明']}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
