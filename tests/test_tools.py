"""Tests for tools."""

import pytest
from src.tools.file_reader import FileReaderTool
from src.tools.regex_tool import RegexTool
from src.tools.token_estimator import TokenEstimatorTool


class TestFileReaderTool:
    """Test FileReaderTool."""

    @pytest.mark.asyncio
    async def test_read_jsonl_file(self, test_corpus_dir):
        """Test reading JSONL files."""
        tool = FileReaderTool(corpus_dir=test_corpus_dir)
        result = await tool.execute(file_path="test.jsonl")

        assert result["success"]
        assert result["format"] == "jsonl"
        assert len(result["content"]) == 2
        assert result["content"][0]["id"] == "1"

    @pytest.mark.asyncio
    async def test_read_markdown_file(self, test_corpus_dir):
        """Test reading markdown files."""
        tool = FileReaderTool(corpus_dir=test_corpus_dir)
        result = await tool.execute(file_path="test.md")

        assert result["success"]
        assert result["format"] == "text"
        assert "# Test" in result["content"]

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, test_corpus_dir):
        """Test reading non-existent file."""
        tool = FileReaderTool(corpus_dir=test_corpus_dir)
        result = await tool.execute(file_path="nonexistent.txt")

        assert not result["success"]
        assert "File not found" in result["error"]

    def test_list_files(self, test_corpus_dir):
        """Test listing files in corpus."""
        tool = FileReaderTool(corpus_dir=test_corpus_dir)
        files = tool.list_files()

        assert len(files) >= 3
        assert "test.jsonl" in files
        assert "test.md" in files
        assert "test.txt" in files


class TestRegexTool:
    """Test RegexTool."""

    @pytest.mark.asyncio
    async def test_find_pattern(self):
        """Test pattern matching."""
        tool = RegexTool()
        result = await tool.execute(
            text="Hello World, this is a test",
            patterns=[r"[Hh]\w+", r"test"],
        )

        assert result["total_matches"] >= 2
        assert len(result["matches"]) > 0

    @pytest.mark.asyncio
    async def test_case_insensitive(self):
        """Test case insensitive matching."""
        tool = RegexTool()
        text = "HELLO hello Hello"
        result = await tool.execute(
            text=text,
            patterns=[r"hello"],
            case_insensitive=True,
        )

        assert result["total_matches"] == 3

    def test_test_pattern(self):
        """Test pattern existence check."""
        tool = RegexTool()
        assert tool.test_pattern("Hello World", r"World")
        assert not tool.test_pattern("Hello World", r"xyz")

    def test_substitute(self):
        """Test pattern substitution."""
        tool = RegexTool()
        result = tool.substitute(
            text="Hello World",
            pattern=r"(\w+) (\w+)",
            replacement=r"\2 \1",
        )

        assert result == "World Hello"


class TestTokenEstimatorTool:
    """Test TokenEstimatorTool."""

    @pytest.mark.asyncio
    async def test_estimate_tokens(self):
        """Test token estimation."""
        tool = TokenEstimatorTool()
        result = await tool.execute(
            text="This is a test string for token estimation."
        )

        assert result["estimated_tokens"] > 0
        assert result["cost_estimate"] > 0
        assert result["model"] == "gpt-4"

    def test_extract_usage_from_response(self):
        """Test extracting usage from API response."""
        tool = TokenEstimatorTool()
        response = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            }
        }

        usage = tool.extract_usage_from_response(response)

        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert usage["total_tokens"] == 150

    def test_get_token_cost(self):
        """Test cost calculation."""
        tool = TokenEstimatorTool()
        cost = tool.get_token_cost(
            input_tokens=1000,
            output_tokens=500,
            input_cost_rate=0.003,
            output_cost_rate=0.006,
        )

        # (1000 * 0.003 + 500 * 0.006) / 1000 = (3 + 3) / 1000 = 0.006
        assert abs(cost - 0.006) < 0.0001
