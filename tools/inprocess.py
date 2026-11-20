"""Make ProcessPoolExecutor run work in the calling thread while tracing, so
coverage and the other tracers see what the optimizer and executor tests do
in their worker processes."""
import concurrent.futures as cf
import pickle


class InlineExecutor(cf.Executor):
    def __init__(self, max_workers=None, mp_context=None, initializer=None, initargs=(), **k):
        if initializer is not None:
            initializer(*pickle.loads(pickle.dumps(initargs)))

    def submit(self, fn, /, *args, **kwargs):
        f = cf.Future()
        try:
            # a real pool pickles the call and its result; do the same so
            # __reduce__ and serde code runs inside the test
            fn, args, kwargs = pickle.loads(pickle.dumps((fn, args, kwargs)))
            f.set_result(pickle.loads(pickle.dumps(fn(*args, **kwargs))))
        except BaseException as e:
            f.set_exception(e)
        return f

    def map(self, fn, *iterables, timeout=None, chunksize=1):
        return [fn(*a) for a in zip(*iterables)]

    def shutdown(self, wait=True, *, cancel_futures=False):
        pass


cf.ProcessPoolExecutor = InlineExecutor
