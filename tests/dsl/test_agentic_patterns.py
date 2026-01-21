"""Tests for DSL agentic patterns (delegate, use, loop).

Test coverage for Phase 1 of the multi-agent pattern support in the DSL:
- delegate keyword for Coordinator/Dispatcher pattern
- use keyword for Hierarchical Task Decomposition pattern
- loop block for Iterative Refinement pattern
"""

import pytest

from streetrace.dsl.grammar.parser import ParserFactory


class TestDelegateKeyword:
    """Test parsing of delegate keyword for agent sub-agents."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_single_delegate(self, parser):
        source = """
agent coordinator:
    tools github
    instruction main_prompt
    delegate worker_agent
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_multiple_delegates(self, parser):
        source = """
agent coordinator:
    tools github
    instruction main_prompt
    delegate worker_a, worker_b, worker_c
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_delegate_with_dotted_name(self, parser):
        source = """
agent coordinator:
    tools github
    instruction main_prompt
    delegate module.worker_agent
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_delegate_with_other_properties(self, parser):
        source = """
agent coordinator:
    tools github, filesystem
    instruction main_prompt
    delegate worker_a, worker_b
    retry default
    timeout 2 minutes
    description "A coordinator agent"
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestUseKeyword:
    """Test parsing of use keyword for agent tool delegation."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_single_use(self, parser):
        source = """
agent orchestrator:
    tools github
    instruction main_prompt
    use helper_agent
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_multiple_use(self, parser):
        source = """
agent orchestrator:
    tools github
    instruction main_prompt
    use helper_a, helper_b
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_use_with_dotted_name(self, parser):
        source = """
agent orchestrator:
    tools github
    instruction main_prompt
    use module.helper_agent
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_use_with_other_properties(self, parser):
        source = """
agent orchestrator:
    tools github
    instruction main_prompt
    use helper_a
    retry default
    description "An orchestrator agent"
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestDelegateAndUse:
    """Test parsing of agents with both delegate and use."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_agent_with_delegate_and_use(self, parser):
        source = """
agent coordinator:
    tools github
    instruction main_prompt
    delegate sub_agent_a, sub_agent_b
    use helper_agent
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestLoopBlock:
    """Test parsing of loop block for iterative refinement."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_loop_with_max_iterations(self, parser):
        source = """
flow refine_result:
    loop max 5 do
        $result = run agent refiner $input
        if $result.quality > 0.9:
            return $result
    end
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_unbounded_loop(self, parser):
        source = """
flow infinite_loop:
    loop do
        $result = run agent processor $input
        if $result.done:
            return $result
    end
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_loop_with_multiple_statements(self, parser):
        source = """
flow complex_loop:
    $counter = 0
    loop max 10 do
        $result = run agent worker $input
        push $result to $results
        if $result.status == "complete":
            return $results
    end
    return $results
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_nested_loop(self, parser):
        source = """
flow nested_loop:
    loop max 3 do
        loop max 5 do
            $result = run agent inner_worker $input
        end
    end
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_loop_in_event_handler(self, parser):
        source = """
on output do
    loop max 3 do
        $check = run validate_output $output
        if $check.passed:
            continue
        retry step $check.message
    end
end
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestDelegateAstTransformation:
    """Test AST transformation for delegate keyword."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_transforms_delegate_to_ast(self, parser):
        from streetrace.dsl.ast.nodes import AgentDef, DslFile
        from streetrace.dsl.ast.transformer import transform

        source = """
agent coordinator:
    tools github
    instruction main_prompt
    delegate worker_a, worker_b
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        agents = [s for s in ast.statements if isinstance(s, AgentDef)]
        assert len(agents) == 1
        agent = agents[0]
        assert agent.name == "coordinator"
        assert agent.delegate == ["worker_a", "worker_b"]

    def test_transforms_single_delegate_to_ast(self, parser):
        from streetrace.dsl.ast.nodes import AgentDef, DslFile
        from streetrace.dsl.ast.transformer import transform

        source = """
agent coordinator:
    tools github
    instruction main_prompt
    delegate worker_agent
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        agents = [s for s in ast.statements if isinstance(s, AgentDef)]
        assert len(agents) == 1
        agent = agents[0]
        assert agent.delegate == ["worker_agent"]

    def test_agent_without_delegate_has_none(self, parser):
        from streetrace.dsl.ast.nodes import AgentDef, DslFile
        from streetrace.dsl.ast.transformer import transform

        source = """
agent simple:
    tools github
    instruction main_prompt
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        agents = [s for s in ast.statements if isinstance(s, AgentDef)]
        assert len(agents) == 1
        agent = agents[0]
        assert agent.delegate is None


class TestUseAstTransformation:
    """Test AST transformation for use keyword."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_transforms_use_to_ast(self, parser):
        from streetrace.dsl.ast.nodes import AgentDef, DslFile
        from streetrace.dsl.ast.transformer import transform

        source = """
agent orchestrator:
    tools github
    instruction main_prompt
    use helper_a, helper_b
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        agents = [s for s in ast.statements if isinstance(s, AgentDef)]
        assert len(agents) == 1
        agent = agents[0]
        assert agent.name == "orchestrator"
        assert agent.use == ["helper_a", "helper_b"]

    def test_transforms_single_use_to_ast(self, parser):
        from streetrace.dsl.ast.nodes import AgentDef, DslFile
        from streetrace.dsl.ast.transformer import transform

        source = """
agent orchestrator:
    tools github
    instruction main_prompt
    use helper_agent
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        agents = [s for s in ast.statements if isinstance(s, AgentDef)]
        assert len(agents) == 1
        agent = agents[0]
        assert agent.use == ["helper_agent"]

    def test_agent_without_use_has_none(self, parser):
        from streetrace.dsl.ast.nodes import AgentDef, DslFile
        from streetrace.dsl.ast.transformer import transform

        source = """
agent simple:
    tools github
    instruction main_prompt
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        agents = [s for s in ast.statements if isinstance(s, AgentDef)]
        assert len(agents) == 1
        agent = agents[0]
        assert agent.use is None


class TestLoopBlockAstTransformation:
    """Test AST transformation for loop block."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_transforms_loop_with_max_to_ast(self, parser):
        from streetrace.dsl.ast.nodes import DslFile, FlowDef, LoopBlock
        from streetrace.dsl.ast.transformer import transform

        source = """
flow refine:
    loop max 5 do
        $result = run agent worker $input
    end
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        assert len(flows) == 1
        flow = flows[0]

        loop_blocks = [s for s in flow.body if isinstance(s, LoopBlock)]
        assert len(loop_blocks) == 1
        loop = loop_blocks[0]
        assert loop.max_iterations == 5
        assert len(loop.body) >= 1

    def test_transforms_unbounded_loop_to_ast(self, parser):
        from streetrace.dsl.ast.nodes import DslFile, FlowDef, LoopBlock
        from streetrace.dsl.ast.transformer import transform

        source = """
flow infinite:
    loop do
        $result = run agent worker $input
        return $result
    end
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        assert len(flows) == 1
        flow = flows[0]

        loop_blocks = [s for s in flow.body if isinstance(s, LoopBlock)]
        assert len(loop_blocks) == 1
        loop = loop_blocks[0]
        assert loop.max_iterations is None
        assert len(loop.body) >= 1

    def test_loop_block_has_source_position(self, parser):
        from streetrace.dsl.ast.nodes import DslFile, FlowDef, LoopBlock
        from streetrace.dsl.ast.transformer import transform

        source = """
flow refine:
    loop max 3 do
        $result = run agent worker $input
    end
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        flow = flows[0]
        loop_blocks = [s for s in flow.body if isinstance(s, LoopBlock)]
        loop = loop_blocks[0]

        assert hasattr(loop, "meta")


class TestLoopBlockNodeCreation:
    """Test LoopBlock AST node creation."""

    def test_loop_block_with_max_iterations(self):
        from streetrace.dsl.ast.nodes import LogStmt, LoopBlock

        loop = LoopBlock(
            max_iterations=5,
            body=[LogStmt(message="Processing")],
        )
        assert loop.max_iterations == 5
        assert len(loop.body) == 1

    def test_loop_block_without_max_iterations(self):
        from streetrace.dsl.ast.nodes import LogStmt, LoopBlock

        loop = LoopBlock(
            max_iterations=None,
            body=[LogStmt(message="Processing")],
        )
        assert loop.max_iterations is None
        assert len(loop.body) == 1

    def test_loop_block_with_source_position(self):
        from streetrace.dsl.ast.nodes import LoopBlock, SourcePosition

        meta = SourcePosition(line=10, column=4)
        loop = LoopBlock(
            max_iterations=3,
            body=[],
            meta=meta,
        )
        assert loop.meta is not None
        assert loop.meta.line == 10
        assert loop.meta.column == 4


class TestAgentDefWithDelegateAndUse:
    """Test AgentDef node creation with delegate and use fields."""

    def test_agent_def_with_delegate(self):
        from streetrace.dsl.ast.nodes import AgentDef

        agent = AgentDef(
            name="coordinator",
            tools=["github"],
            instruction="main_prompt",
            delegate=["worker_a", "worker_b"],
        )
        assert agent.delegate == ["worker_a", "worker_b"]
        assert agent.use is None

    def test_agent_def_with_use(self):
        from streetrace.dsl.ast.nodes import AgentDef

        agent = AgentDef(
            name="orchestrator",
            tools=["github"],
            instruction="main_prompt",
            use=["helper_a"],
        )
        assert agent.use == ["helper_a"]
        assert agent.delegate is None

    def test_agent_def_with_both_delegate_and_use(self):
        from streetrace.dsl.ast.nodes import AgentDef

        agent = AgentDef(
            name="complex",
            tools=["github"],
            instruction="main_prompt",
            delegate=["sub_agent"],
            use=["helper_agent"],
        )
        assert agent.delegate == ["sub_agent"]
        assert agent.use == ["helper_agent"]

    def test_agent_def_without_delegate_or_use(self):
        from streetrace.dsl.ast.nodes import AgentDef

        agent = AgentDef(
            name="simple",
            tools=["github"],
            instruction="main_prompt",
        )
        assert agent.delegate is None
        assert agent.use is None
