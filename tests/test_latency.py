import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),".."))

from bridge.shm_reader import ShmReader


def percentile(sorted_data: list[float], p: float) -> float:

    idx = (p / 100)* (len(sorted_data) -1)
    lo = int(idx)
    hi = min(lo + 1, len (sorted_data) -1)
    frac = idx - lo
    return sorted_data[lo] * (1 - frac) + sorted_data[hi] * frac

def run_benchmark(sample_count: int = 1000) -> None:
    print (f"=== Aegis-Link Gecikme Benchmark ({sample_count} örnek) ===\n")

    latencies_us: list[float] = []
    last_frame_id = -1

    with ShmReader() as reader:
        print("Bağlantı kuruldu. Örnekler toplanıyor...\n")

        while len (latencies_us) < sample_count:
            snap= reader.read()

            if snap.frame_id == last_frame_id:
                time.sleep(0.0005)
                continue
            last_frame_id = snap.frame_id

            latency_ns = snap.read_at_ns - snap.timestamps_ns
            latency_us = latency_ns / 1_000.0

            if latency_us > 0:
                latencies_us.append(latency_us)
            time.sleep (0.0005)

    if not latencies_us:
        print("[HATA] Hiç geçerli ölçüm alınamadı.")
        return

    latencies_us.sort()
    n = len(latencies_us)

    avg = sum(latencies_us) / n 
    median = percentile (latencies_us, 50)
    p95 =percentile(latencies_us, 95)
    p99 =percentile(latencies_us, 99)
    mn = latencies_us [0]
    mx = latencies_us [-1]

    TARGET_P99_US = 10_000.0

    print(f"{'Örnekler':<20} {n}")
    print(f"{'Ortalama':<20} {avg:>8.1f} μs")
    print(f"{'Medyan (P50)':<20}: {median:>8.1f} µs")
    print(f"{'P95':<20}: {p95:>8.1f} µs")
    print(f"{'P99':<20}: {p99:>8.1f} µs")
    print(f"{'Min':<20}: {mn:>8.1f} µs")
    print(f"{'Max':<20}: {mx:>8.1f} µs")
    print()

    passed = p99 < TARGET_P99_US
    status = " GEÇTİ " if passed else " BAŞARISIZ "
    print(f"Hedef (P99 < 10ms): {status}")

    if not passed:
        print (f" -> P99 hedefe {p99 - TARGET_P99_US: .1f} µs uzakta. ")

if __name__ == "__main__":
    sample_count = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    run_benchmark (sample_count)
