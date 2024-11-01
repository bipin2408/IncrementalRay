import time
import logging
import os

import ray
ray.init()

# Set up logging
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# S1 = "CLASS"
# S2 = "LABS"
S1 = "A"*3000
S2 = "A"*3000
bsize = 100

# Create log filename with dimensions and block size
log_filename = f'lcs_{len(S1)}x{len(S2)}_bsize{bsize}.log'
log_path = os.path.join(log_dir, log_filename)

# Remove old log if it exists
if os.path.exists(log_path):
    os.remove(log_path)

logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

@ray.remote
def lcs(X, Y, bleft, bup, bsize, Lleft, Lup, Ldiag):
    """
        :param X, Y: input strings
        :param (bleft, bup): block index
        :param bsize: size of the block: bsize*bsize
        :param Lleft: left block
        :param Lup: up block
        :param Ldiag: diagonal block

        :return: outputs block at the input block index
    """
    logging.info(f"Starting block calculation: (bleft={bleft}, bup={bup})")
    # Declaring the array for storing the dp values
    L = [[None] * bsize for i in range(bsize)]

    def l(i, j):
        if i >= 0 and j >= 0:
            return L[i][j] #current block
        if i < 0 and j < 0:
            val = Ldiag[bsize+i][bsize+j] if Ldiag is not None else 0 #diagonal block
            logging.info(f"  Using diagonal value at ({i},{j}): {val}")
            return val
        if i < 0:
            val = Lleft[bsize+i][j] if Lleft is not None else 0 #left block
            logging.info(f"  Using left value at ({i},{j}): {val}")
            return val
        val = Lup[i][bsize+j] if Lup is not None else 0 #up block
        logging.info(f"  Using up value at ({i},{j}): {val}")
        return val

    # Following steps build L[m+1][n+1] in bottom up fashion
    # Note: L[i][j] contains length of LCS of X[0..i-1]
    # and Y[0..j-1]
    #main algo
    for i in range(bsize):
        for j in range(bsize):
            left = bleft*bsize + i
            up = bup*bsize + j
            if left == 0 or up == 0:
                L[i][j] = 0
                logging.info(f"  Setting boundary value L[{i}][{j}] = 0")
            if X[left-1] == Y[up-1]:
                L[i][j] = l(i-1, j-1) + 1
                logging.info(f"  Characters match at ({left-1},{up-1}): L[{i}][{j}] = {L[i][j]}")
            else:
                L[i][j] = max(l(i-1, j), l(i, j-1))
                logging.info(f"  Characters don't match: L[{i}][{j}] = {L[i][j]}")

    logging.info(f"Completed block (bleft={bleft}, bup={bup})")
    return L

# Driver code
if __name__ == '__main__':
    logging.info("Starting LCS calculation...")
    logging.info(f"Input strings: length(S1)={len(S1)}, length(S2)={len(S2)}")

    m = len(S1)
    n = len(S2)
    logging.info(f"Using block size: {bsize}")
    
    assert m % bsize == 0
    assert n % bsize == 0
    logging.info(f"Grid size will be: {m//bsize} x {n//bsize} blocks")

    X = ray.put(S1)
    Y = ray.put(S2)
    logging.info("Strings distributed to Ray cluster")

    f = [[None] * (n//bsize + 1) for i in range(m//bsize + 1)]

    start = time.time()
    logging.info("\nStarting block calculations:")
    for bleft in range(0, m//bsize):
        for bup in range(0, n//bsize):
            logging.info(f"\nProcessing block ({bleft},{bup}):")
            fleft = f[bleft-1][bup] if bleft > 0 else None
            fup = f[bleft][bup-1] if bup > 0 else None
            fdiag = f[bleft-1][bup-1] if bleft > 0 and bup > 0 else None
            
            logging.info(f"  Using references: left={'Yes' if fleft else 'No'}, "
                        f"up={'Yes' if fup else 'No'}, "
                        f"diagonal={'Yes' if fdiag else 'No'}")

            f[bleft][bup] = lcs.remote(X, Y, bleft, bup, bsize, fleft, fup, fdiag)

    logging.info("\nWaiting for final result...")
    L = ray.get(f[m//bsize-1][n//bsize-1])
    elapsed = time.time() - start
    
    final_result = f"\nFinal Results:\nLength of LCS is {L[bsize-1][bsize-1]} bsize: {bsize} time: {elapsed:.2f}"
    print(final_result) 
    logging.info(final_result)

# This repeats the Figure 10 of CIEL. We see that the optimum block size is
# somewhere in the middle. When we have high block size, the workers sit idle.
# When we have low block size, the co-ordination overhead starts to matter.
#
# 10 -> 10.83
# 15 -> 5.10
# 30 -> 1.33
# 50 -> 1.24
# 60 -> 0.70
# 100 -> 0.46
# 300 -> 0.53
# 600 -> 0.75
# 1000 -> 1.11
# 1500 -> 1.36
# 3000 -> 1.63