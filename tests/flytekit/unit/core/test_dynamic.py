import typing

from flytekit import dynamic
from flytekit.core import context_manager
from flytekit.core.context_manager import ExecutionState, FastSerializationSettings, Image, ImageConfig
from flytekit.core.task import task
from flytekit.core.type_engine import TypeEngine
from flytekit.core.workflow import workflow


def test_wf1_with_fast_dynamic():
    @task
    def t1(a: int) -> str:
        a = a + 2
        return "fast-" + str(a)

    @dynamic
    def my_subwf(a: int) -> typing.List[str]:
        s = []
        for i in range(a):
            s.append(t1(a=i))
        return s

    @workflow
    def my_wf(a: int) -> typing.List[str]:
        v = my_subwf(a=a)
        return v

    with context_manager.FlyteContextManager.with_context(
        context_manager.FlyteContextManager.current_context().with_serialization_settings(
            context_manager.SerializationSettings(
                project="test_proj",
                domain="test_domain",
                version="abc",
                image_config=ImageConfig(Image(name="name", fqn="image", tag="name")),
                env={},
                fast_serialization_settings=FastSerializationSettings(enabled=True),
            )
        )
    ) as ctx:
        with context_manager.FlyteContextManager.with_context(
            ctx.with_execution_state(
                ctx.execution_state.with_params(
                    mode=ExecutionState.Mode.TASK_EXECUTION,
                    additional_context={
                        "dynamic_addl_distro": "s3://my-s3-bucket/fast/123",
                        "dynamic_dest_dir": "/User/flyte/workflows",
                    },
                )
            )
        ) as ctx:
            input_literal_map = TypeEngine.dict_to_literal_map(ctx, {"a": 5})
            dynamic_job_spec = my_subwf.dispatch_execute(ctx, input_literal_map)
            assert len(dynamic_job_spec._nodes) == 5
            assert len(dynamic_job_spec.tasks) == 1
            args = " ".join(dynamic_job_spec.tasks[0].container.args)
            assert args.startswith(
                "pyflyte-fast-execute --additional-distribution s3://my-s3-bucket/fast/123 "
                "--dest-dir /User/flyte/workflows"
            )

    assert context_manager.FlyteContextManager.size() == 1