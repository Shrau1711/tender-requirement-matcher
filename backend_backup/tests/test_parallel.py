import threading
import time

from app.services.llm import Reply
from app.services.llm_cache import CachedLLM
from app.services.parallel import run_parallel


def test_results_come_back_in_job_order():
    def slow_first(n: int) -> int:
        time.sleep(0.05 if n == 0 else 0)
        return n * 2

    assert run_parallel(slow_first, [0, 1, 2, 3]) == [0, 2, 4, 6]


def test_jobs_really_overlap():
    started = threading.Barrier(3, timeout=2)  # every job waits for the other two, so it only passes if they overlap
    assert run_parallel(lambda n: started.wait() >= 0, [1, 2, 3], workers=3) == [True, True, True]


def test_the_cache_counts_calls_correctly_across_threads(tmp_path):
    class Slow:
        model = "m"

        def generate(self, system: str, user: str) -> Reply:
            return Reply(text=user, input_tokens=1, output_tokens=1)

    llm = CachedLLM(Slow(), tmp_path)
    run_parallel(lambda n: llm.generate("s", str(n)), range(40))
    assert llm.calls == 40 and llm.input_tokens == 40