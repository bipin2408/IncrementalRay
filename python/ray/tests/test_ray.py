import ray
print("Ray is imported from:", ray.__file__)


@ray.remote(incremental=True)
def compute_heavy(x):
    print(f"Computing heavy operation for {x}")
    return x * x

ray.init()
ray.workflow.init(storage='file:///tmp/ray/workflow_data')

# First call (computes and caches the result)
result1 = ray.get(compute_heavy.remote(5))
print("Result 1:", result1)

# Second call (retrieves the result from cache)
result2 = ray.get(compute_heavy.remote(5))
print("Result 2:", result2)