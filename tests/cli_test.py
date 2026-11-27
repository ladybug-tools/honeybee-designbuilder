"""Test the CLI commands"""
import os
from click.testing import CliRunner

from honeybee_designbuilder.cli.translate import model_to_dsbxml_cli


def test_model_to_dsbxml_cli():
    """Test the translation of a Model to INP."""
    runner = CliRunner()
    input_hb_model = './tests/assets/small_revit_sample.hbjson'
    project_info = './tests/assets/project_info.json'
    out_file = './tests/assets/cli_test.xml'

    in_args = [
        input_hb_model, '--project-info', project_info,
        '--program-name', 'Ladybug Tools', '--output-file', out_file
    ]
    result = runner.invoke(model_to_dsbxml_cli, in_args)

    assert result.exit_code == 0
    assert os.path.isfile(out_file)
    os.remove(out_file)
