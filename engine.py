"""Local simulation and RBF surrogate. No cloud service or API key required."""
import math
import time
from contextvars import ContextVar
from collections import deque
import numpy as np
from physics import DEFAULTS, Solver

FEATURES = ['Omegaeh', 'Fah', 'Epsilon33']
BOUNDS = np.array([[0.7, 1.3], [0.02, 0.12], [0.02, 0.08]])
REQUEST_DEADLINE = ContextVar('request_deadline', default=None)
REQUEST_PROGRESS = ContextVar('request_progress', default=None)

def parameters(values):
    p = dict(DEFAULTS)
    for key, value in values.items():
        if key not in p:
            raise ValueError('未知参数: ' + key)
        n = float(value)
        if not math.isfinite(n):
            raise ValueError('参数必须是有限数值')
        if key in ('NT_total', 'NT_start', 'NN'):
            if not n.is_integer():
                raise ValueError('计算参数必须是整数')
            n = int(n)
        p[key] = n
    if not 10 <= p['NT_total'] <= 40000 or not 32 <= p['NN'] <= 512:
        raise ValueError('总周期需为10–40000，每周期步数需为32–512')
    if not 0 <= p['NT_start'] < p['NT_total'] - 2:
        raise ValueError('开始输出周期须小于总周期减2')
    if not 0.1 <= p['Omegaeh'] <= 5 or not 0 <= p['Omegaet'] <= 5:
        raise ValueError('激励频率超出原型支持范围')
    for key in p:
        if key.startswith(('Epsilon', 'K', 'H')) and p[key] < 0:
            raise ValueError('阻尼、刚度、间隙不能为负')
        if abs(p[key]) > 10000 and key not in ('NT_total', 'NT_start', 'NN'):
            raise ValueError('参数绝对值过大')
    return p

def simulate(values):
    p = parameters(values)
    solver = Solver()
    y = [0.] * 6
    period = 2 * math.pi / p['Omegaeh']
    dt = period / p['NN']
    rows = np.empty(((p['NT_total'] - p['NT_start']) * p['NN'], 3))
    section = []
    output_index = 0
    started = time.perf_counter()
    total = p['NT_total'] * p['NN']
    sample_stride = max(1, math.ceil(len(rows) / 2200))
    state_samples = []
    state_tail = deque(maxlen=8 * p['NN'])
    progress = REQUEST_PROGRESS.get()
    # Preserve the original derivative and RK integration. Timestamp is the physical endpoint of the completed RK4 step. The supplied Tk app labels this same sample with the step start time, which is a one-dt axis shift.
    for step in range(p['NT_total'] * p['NN']):
        if progress and step % 4096 == 0:
            progress(dict(stage='integrating', completed=step, total=total))
        if step % 1024 == 0 and REQUEST_DEADLINE.get() is not None and time.monotonic() > REQUEST_DEADLINE.get():
            raise ValueError('计算超时，请减少周期、步数或实验组数后重试')
        y = solver.RK4(y, step * dt, dt, p)
        if not all(math.isfinite(v) and abs(v) < 1e8 for v in y):
            raise ValueError('积分发散，请减小步长或调整参数')
        if step >= p['NT_start'] * p['NN']:
            state = [(step + 1) * dt, *y]
            state_tail.append(state)
            if output_index % sample_stride == 0:
                state_samples.append(state)
            rows[output_index] = [(step + 1) * dt, y[4], y[5]]
            output_index += 1
            if (step + 1) % p['NN'] == 0:
                section.append([y[4], y[5]])
    a = rows
    if progress:
        progress(dict(stage='analysis', completed=total, total=total))
    signal = a[:, 1]
    centered = signal - signal.mean()
    window = np.hanning(len(signal))
    power = abs(np.fft.rfft(centered * window)) ** 2 / max(float((window ** 2).sum()), 1)
    freq = np.fft.rfftfreq(len(signal), dt)
    peak = int(np.argmax(power[1:]) + 1)
    stride = max(1, math.ceil(len(a) / 2200))
    # A global stride can skip almost whole periods and connect unrelated phases.
    # Keep every integration sample in a short, contiguous final-time window.
    phase_count = min(len(a), 8 * p['NN'])
    phase_rows = a[-phase_count:]
    segments = np.array_split(a, min(24, len(a)))
    rms_windows = [[float(segment[-1, 0]), float(np.sqrt(np.mean(segment[:, 1] ** 2)))] for segment in segments]
    counts, histogram_edges = np.histogram(signal, bins=24)
    histogram = np.column_stack([(histogram_edges[:-1]+histogram_edges[1:])/2, counts]).tolist()
    # Keep strongest bin per frequency interval to preserve peaks in compact charts.
    edges = np.linspace(0, len(freq), min(len(freq), 2200) + 1, dtype=int)
    bins = [left + int(np.argmax(power[left:right])) for left, right in zip(edges[:-1], edges[1:]) if right > left]
    return dict(params=p, stats=dict(rms=float(np.sqrt(np.mean(signal**2))),
        peak=float(np.max(np.abs(signal))), mean=float(signal.mean()),
        dominant_frequency=float(freq[peak]), points=len(signal), seconds=time.perf_counter()-started),
        series=a[::stride].tolist(), spectrum=np.column_stack([freq[bins], power[bins]]).tolist(),
        phase=phase_rows[:, 1:3].tolist(),
        states=state_samples, state_tail=list(state_tail),
        analysis=dict(rms_windows=rms_windows, histogram=histogram),
        poincare=section, sampling=dict(dt=dt, period=period, chart_stride=stride, time_convention="completed RK4 step endpoint; NT_start transient cycles discarded",
            phase_stride=1, phase_points=phase_count,
            phase_cycles=phase_count / p['NN'],
            phase_time_start=float(phase_rows[0, 0]), phase_time_end=float(phase_rows[-1, 0])))

def normalize(x):
    return (np.asarray(x) - BOUNDS[:, 0]) / (BOUNDS[:, 1] - BOUNDS[:, 0])

def kernel(x, centers, width=.45):
    return np.exp(-np.sum((np.asarray(x)[:, None, :] - centers[None, :, :])**2, axis=2) / (2 * width**2))

def train_and_recommend(values, count=36):
    base = parameters(values)
    if base['NT_total'] * base['NN'] * (count + 2) > 12000000:
        raise ValueError('代理模型训练需重复运行38次。当前计算量较大，请先点击“快速试算配置”或自行减少周期，再开始训练。手动单次仿真支持原始默认值。')
    xbase = np.array([base[k] for k in FEATURES])
    if np.any(xbase < BOUNDS[:, 0]) or np.any(xbase > BOUNDS[:, 1]):
        raise ValueError('AI实验范围：Omegaeh 0.7–1.3；Fah 0.02–0.12；Epsilon33 0.02–0.08')
    rng = np.random.default_rng(1024)
    x = rng.uniform(BOUNDS[:, 0], BOUNDS[:, 1], (count, 3))
    y = []
    for row in x:
        p = dict(base, **dict(zip(FEATURES, row.tolist())))
        y.append(simulate(p)['stats']['rms'])
    y = np.array(y)
    z = normalize(x)
    train, test = np.arange(27), np.arange(27, count)
    centers = z[train]
    # Select hyperparameters by cross-validation within the 27 training cases only.
    choices = []
    for width in (.3, .45, .7, 1., 2.):
        for ridge in (.001, .01, .1):
            errors = []
            for fold in range(3):
                valid = train[train % 3 == fold]
                fit = train[train % 3 != fold]
                mean = y[fit].mean()
                weights = np.linalg.solve(kernel(z[fit], z[fit], width) + ridge*np.eye(len(fit)), y[fit]-mean)
                errors.extend(abs(mean+kernel(z[valid], z[fit], width) @ weights-y[valid]))
            choices.append((float(np.mean(errors)), width, ridge))
    cv_mae, width, ridge = min(choices)
    mean = y[train].mean()
    mat = kernel(centers, centers, width)
    weights = np.linalg.solve(mat + ridge * np.eye(len(train)), y[train]-mean)
    pred = mean + kernel(z[test], centers, width) @ weights
    mae = float(np.mean(abs(pred - y[test])))
    baseline_mae = float(np.mean(abs(y[test] - y[train].mean())))
    # Only damping is a design variable: do not reduce external forcing to manufacture improvement.
    candidates = np.tile(xbase, (101, 1))
    candidates[:, 2] = np.linspace(*BOUNDS[2], 101)
    estimates = mean + kernel(normalize(candidates), centers, width) @ weights
    selected = candidates[int(np.argmin(estimates))]
    chosen = dict(base, **dict(zip(FEATURES, selected.tolist())))
    before, after = simulate(base), simulate(chosen)
    improvement = (before['stats']['rms'] - after['stats']['rms']) / max(before['stats']['rms'], 1e-12) * 100
    return dict(model='RBF核岭回归', features=FEATURES, bounds=BOUNDS.tolist(), seed=1024,
        train_count=len(train), test_count=len(test), mae=mae, baseline_mae=baseline_mae,
        hyperparameters=dict(width=width, ridge=ridge, training_cv_mae=cv_mae),
        validation=[dict(actual=float(y[i]), predicted=float(v)) for i,v in zip(test,pred)],
        recommended=chosen, predicted_rms=float(estimates.min()), before=before['stats'],
        after=after['stats'], improvement_percent=improvement,
        useful=mae < baseline_mae, improved=improvement > 0,
        note='仿真数据上的代理模型；仅优化Epsilon33，保持激励不变。独立留出集仅9个样本，不能证明真实工程效果。不同积分时长需重新训练。')
