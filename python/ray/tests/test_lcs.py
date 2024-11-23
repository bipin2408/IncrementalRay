import time
import ray
from ray.experimental.internal_kv import _internal_kv_initialized, _internal_kv_get, _internal_kv_put, _internal_kv_list, _internal_kv_del

# Initialize Ray
ray.init(
    local_mode=True,
    ignore_reinit_error=True,
    include_dashboard=False,
    num_cpus=1
)

if not _internal_kv_initialized():
    raise RuntimeError("Internal KV store not initialized properly")

# Test input strings
S1 = "A"*30
S2 = "A"*30
bsize = 10

@ray.remote(incremental=True)
def lcs(X, Y, bleft, bup, bsize, Lleft, Lup, Ldiag):
    """LCS computation for a single block."""
    L = [[None] * bsize for i in range(bsize)]

    def l(i, j):
        if i >= 0 and j >= 0:
            return L[i][j]
        if i < 0 and j < 0:
            val = Ldiag[bsize+i][bsize+j] if Ldiag is not None else 0
            return val
        if i < 0:
            val = Lleft[bsize+i][j] if Lleft is not None else 0
            return val
        val = Lup[i][bsize+j] if Lup is not None else 0
        return val

    x_start = bleft * bsize
    y_start = bup * bsize
    
    X_data = ray.get(X) if isinstance(X, ray.ObjectRef) else X
    Y_data = ray.get(Y) if isinstance(Y, ray.ObjectRef) else Y
    
    for i in range(bsize):
        for j in range(bsize):
            left = bleft*bsize + i
            up = bup*bsize + j
            if left == 0 or up == 0:
                L[i][j] = 0
            elif X_data[left-1] == Y_data[up-1]:
                L[i][j] = l(i-1, j-1) + 1
            else:
                L[i][j] = max(l(i-1, j), l(i, j-1))

    return L

def clear_cache():
    """Clear all cached blocks."""
    prefix = b"cache:lcs"  
    for key in _internal_kv_list(prefix):
        _internal_kv_del(key)
    print("Cache cleared")


if __name__ == '__main__':
    clear_cache()
    print("Starting LCS calculation...")
    print(f"Grid size will be: {len(S1)//bsize} x {len(S2)//bsize} blocks")

    m = len(S1)
    n = len(S2)
    X = ray.put(S1)
    Y = ray.put(S2)

    # First run
    print("\nFirst run starting...")
    f = [[None] * (n//bsize + 1) for i in range(m//bsize + 1)]
    start_time1 = time.time()
    
    for bleft in range(0, m//bsize):
        for bup in range(0, n//bsize):
            block_key = f"cache:lcs:block_{bleft}_{bup}".encode()
            
            fleft = f[bleft-1][bup] if bleft > 0 else None
            fup = f[bleft][bup-1] if bup > 0 else None
            fdiag = f[bleft-1][bup-1] if bleft > 0 and bup > 0 else None
            
            result = lcs.remote(X, Y, bleft, bup, bsize, fleft, fup, fdiag)
            block_result = ray.get(result)
            
            _internal_kv_put(block_key, ray.cloudpickle.dumps(block_result))
            f[bleft][bup] = block_result

    L1 = f[m//bsize-1][n//bsize-1]
    elapsed1 = time.time() - start_time1
    print(f" First run result: {L1[bsize-1][bsize-1]}, Duration: {elapsed1:.2f}s")

    # Second run
    print("\nSecond run starting...")
    f = [[None] * (n//bsize + 1) for i in range(m//bsize + 1)]
    start_time2 = time.time()
    
    for bleft in range(0, m//bsize):
        for bup in range(0, n//bsize):
            block_key = f"cache:lcs:block_{bleft}_{bup}".encode()
            
            cached_result = _internal_kv_get(block_key)
            if cached_result:
                f[bleft][bup] = ray.cloudpickle.loads(cached_result)
                continue
                
            fleft = f[bleft-1][bup] if bleft > 0 else None
            fup = f[bleft][bup-1] if bup > 0 else None
            fdiag = f[bleft-1][bup-1] if bleft > 0 and bup > 0 else None
            
            result = lcs.remote(X, Y, bleft, bup, bsize, fleft, fup, fdiag)
            block_result = ray.get(result)
            
            _internal_kv_put(block_key, ray.cloudpickle.dumps(block_result))
            f[bleft][bup] = block_result

    L2 = f[m//bsize-1][n//bsize-1]
    elapsed2 = time.time() - start_time2
    print(f" Second run result: {L2[bsize-1][bsize-1]}, Duration: {elapsed2:.2f}s")
    
    results_match = L1[bsize-1][bsize-1] == L2[bsize-1][bsize-1]
    speedup = elapsed1 / elapsed2 if elapsed2 > 0 else float('inf')
    print(f"\nResults match: {results_match}")
    print(f"Speedup factor: {speedup:.2f}x")

    print("\nThird run starting (with modified input)...")
    S1_modified = S1[:15] + 'B' + S1[16:]
    X_modified = ray.put(S1_modified)
    
    f = [[None] * (n//bsize + 1) for i in range(m//bsize + 1)]
    start_time3 = time.time()
    modified_row = 15 // bsize  
    
    for bleft in range(0, m//bsize):
        for bup in range(0, n//bsize):
            block_key = f"cache:lcs:block_{bleft}_{bup}".encode()
            if bleft >= modified_row:  #
                cached_result = None
            else:
                cached_result = _internal_kv_get(block_key)
                if cached_result:
                    f[bleft][bup] = ray.cloudpickle.loads(cached_result)
                    continue
            
            fleft = f[bleft-1][bup] if bleft > 0 else None
            fup = f[bleft][bup-1] if bup > 0 else None
            fdiag = f[bleft-1][bup-1] if bleft > 0 and bup > 0 else None
            
            result = lcs.remote(X_modified, Y, bleft, bup, bsize, fleft, fup, fdiag)
            block_result = ray.get(result)
            
            if bleft < modified_row:
                _internal_kv_put(block_key, ray.cloudpickle.dumps(block_result))
            f[bleft][bup] = block_result

    L3 = f[m//bsize-1][n//bsize-1]
    elapsed3 = time.time() - start_time3
    print(f" Third run result: {L3[bsize-1][bsize-1]}, Duration: {elapsed3:.2f}s")
    print(f"Change in result: {L2[bsize-1][bsize-1] - L3[bsize-1][bsize-1]}")
    print(f"Speedup vs first run: {elapsed1/elapsed3:.2f}x")