# Rays execution flow

## 1. Initialization
When we call 


 `@ray.remote` creates a stateless task when it is called on a function but a stateful actor when it is called on a class method.
 A task is executed asynchronously with the caller: the `.remote()` call immediately returns one or more `ObjectRefs` (futures) that can be used to retrieve the return value(s).

 Objects are application value that are either returned by a task or created by the `@ray.put` call. they are **immutable** and can be called by the workers using the *ObjectRefs*

 Each worker process and raylet is assigned a unique 28-byte identifier and an IP address and port. The same address and port can be reused by subsequent components (e.g., if a previous worker process dies), but the unique IDs are never reused (i.e., they are tombstoned upon process death). Worker processes fate-share with their local raylet process.


Code references:

    Core worker source code: IncrementalRay/src/ray/core_worker/core_worker.h. This code is the backbone for the various protocols involved in task dispatch, actor task dispatch, the in-process store, and memory management.
    Language bindings for Python: IncrementalRay/python/ray/includes/libcoreworker.pxd



## 2. Task Definition

Fucntions that are decorated with `@ray.remote` are called *task* functions that can be executed remotely.

Python Layer: The task submission begins in the Python code, where the function decorated with @ray.remote is called with .remote(). This eventually calls worker.core_worker.submit_task().
File: IncrementalRay/python/ray/remote_function.py

```python
# python/ray/remote_function.py
class RemoteFunction:
    ...
    def remote(self, *args, **kwargs):
        return self._remote(args=args, kwargs=kwargs)
```



C++ Core Worker: The submit_task() method in the Python CoreWorker class is a wrapper that interfaces with the C++ Core Worker. In the C++ layer, CoreWorker::SubmitTask in IncrementalRay/src/ray/core_worker/core_worker.cc is called.

``` c++
// src/ray/core_worker/core_worker.cc

std::vector<rpc::ObjectReference> CoreWorker::SubmitTask(
    const RayFunction &function,
    const std::vector<std::unique_ptr<TaskArg>> &args,
    const TaskOptions &task_options,
    int max_retries,
    bool retry_exceptions,
    const rpc::SchedulingStrategy &scheduling_strategy,
    const std::string &debugger_breakpoint,
    const std::string &serialized_retry_exception_allowlist,
    const TaskID current_task_id) {
  RAY_CHECK(scheduling_strategy.scheduling_strategy_case() !=
            rpc::SchedulingStrategy::SchedulingStrategyCase::SCHEDULING_STRATEGY_NOT_SET);

  // 1. Create a TaskSpecBuilder to build the task specification.
  TaskSpecBuilder builder;
  const auto next_task_index = worker_context_.GetNextTaskIndex();

  // 2. Generate a unique TaskID for the new task.
  const auto task_id = TaskID::ForNormalTask(
      worker_context_.GetCurrentJobID(),
      worker_context_.GetCurrentInternalTaskId(),
      next_task_index);

  // 3. Handle resource constraints and task naming.
  auto constrained_resources =
      AddPlacementGroupConstraint(task_options.resources, scheduling_strategy);
  auto task_name = task_options.name.empty()
                       ? function.GetFunctionDescriptor()->DefaultTaskName()
                       : task_options.name;

  // 4. Build the common task specification.
  BuildCommonTaskSpec(builder,
                      worker_context_.GetCurrentJobID(),
                      task_id,
                      task_name,
                      current_task_id != TaskID::Nil() ? current_task_id
                                                       : worker_context_.GetCurrentTaskID(),
                      next_task_index,
                      GetCallerId(),
                      rpc_address_,
                      function,
                      args,
                      task_options.num_returns,
                      constrained_resources,
                      task_options.placement_resources,
                      debugger_breakpoint,
                      worker_context_.GetTaskDepth() + 1,
                      serialized_runtime_env_info_,
                      worker_context_.GetMainThreadOrActorCreationTaskID(),
                      task_options.concurrency_group_name,
                      task_options.include_job_config,
                      task_options.generator_backpressure_num_objects,
                      task_options.enable_task_events);

  // 5. Build the TaskSpecification object from the builder.
  TaskSpecification task_spec = builder.Build();

    // Log the task submission
    RAY_LOG(DEBUG) << "Submitting normal task " << task_spec.DebugString();

    // Initializes a vector to store references to the task's return objects.
    std::vector<rpc::ObjectReference> returned_refs;

    if (options_.is_local_mode) {
      // Execute the task locally without Ray cluster
      returned_refs = ExecuteTaskLocalMode(task_spec);
    } else {
      // Add the task to the task manager's pending tasks
      returned_refs = task_manager_->AddPendingTask(
          task_spec.CallerAddress(), task_spec, CurrentCallSite(), max_retries);

      // Post the task submission to the IO service event loop
      io_service_.post(
          [this, task_spec]() {
            // Submit the task using the normal task submitter
            RAY_UNUSED(normal_task_submitter_->SubmitTask(task_spec));
          },
          "CoreWorker.SubmitTask");
    }

    return returned_refs;
  }
```

So if *options_.is_local_mode* is true, the task is executed synchronously in the local process without using Ray's distributed scheduling.
The method *ExecuteTaskLocalMode(task_spec)* handles this execution.

If not in local mode, the task submission proceeds using Ray's distributed execution framework.

It then adds the tasks to the TaskManager's pending tasks that manages the task metadata and handles retries upon failures. it returns references to the task's output objects. So the TaskManager keeps track of all the tasks that have been submitted but not completed and bookkeeping for task retries also.
This task manager is local, more specifically it is a member of the CoreWorker class.

`io_service_.post(...)`
Schedules the provided lambda function to be executed in the IO service's event loop. This ensures that task submission is non-blocking and handled asynchronously.
Lambda Function:
Captures this pointer and task_spec by value.
Calls normal_task_submitter_->SubmitTask(task_spec) to submit the task.
RAY_UNUSED is used to explicitly ignore the return value of SubmitTask.

`return returned_refs;`
Returns the references to the task's output objects to the caller.
These references can be used to fetch the actual results once the task execution is complete.


NormalTaskSubmitter: The NormalTaskSubmitter::SubmitTask method in normal_task_submitter.cc handles the actual submission of normal tasks. It resolves dependencies, queues the task, and manages worker leases.
File: IncrementalRay/src/ray/core_worker/transport/normal_task_submitter.cc
