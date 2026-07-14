"""Keep shipped examples aligned with the supported script contract."""

from pathlib import Path

from uvs.uvs import parse_pep723_header, read_script_source, validate_script_has_main


def test_all_examples_are_supported_scripts():
    examples = sorted((Path(__file__).parents[1] / "examples").glob("*.py"))
    assert examples, "at least one public example is required"

    for example in examples:
        metadata = parse_pep723_header(example)
        assert set(metadata) <= {"dependencies", "requires-python", "tool"}
        assert validate_script_has_main(read_script_source(example))
