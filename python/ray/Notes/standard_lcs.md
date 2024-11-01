- Each block computes its values using:
    - Values from its own block, left neighbor (Lleft), upper neighbor (Lup), diagonal neighbor (Ldiag)
  - Parallelization Strategy:
    - The matrix is divided into blocks of size bsize × bsize
    - Each block can be computed independently once its dependencies (left, up, diagonal) are ready
    - Ray handles the parallel execution of these blocks
    - Blocks are computed in a wave pattern from top-left to bottom-right

  > small blocks tend to have more parallelism but more overhead and large blocks have less parallelism but less overhead


Grid with small blocks (bsize=10):
┌─┬─┬─┬─┬─┐
├─┼─┼─┼─┼─┤
├─┼─┼─┼─┼─┤
├─┼─┼─┼─┼─┤
└─┴─┴─┴─┴─┘
More Overhead Because:
- Communication Cost:
  - More blocks = more messages between workers
  - Each block needs to wait for and fetch data from 3 neighbors
  - Ray needs to manage more remote objects
- Task Scheduling:
  - More blocks = more tasks to schedule
  - Ray's scheduler has more work to coordinate
  - More context switching between tasks
- Memory Management:
  - Each block creates separate memory allocations
  - More garbage collection overhead
  - More serialization/deserialization of data

That is why block size 100 is optimal, because enough parallelism to use available cores, large enough blocks to minimize overhead, good cache and memory utilization.
that is why we see 
> 10 -> 10.83s (too much overhead)

> 100 -> 0.46s (optimal balance)

> 3000 -> 1.63s (not enough parallelism)