"""honeybee-designbuilder translation commands."""
import sys
import logging
import click
import base64

from honeybee.model import Model
import honeybee_designbuilder.writer as model_writer

_logger = logging.getLogger(__name__)


@click.group(help='Commands for translating Honeybee Model to DesignBuilder formats.')
def translate():
    pass


@translate.command('model-to-dsbxml')
@click.argument('model-file', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option(
    '--xml-template', '-t', help='Text for the type of template file to be used '
    'to write the dsbXML. Different templates contain different amounts of default '
    'assembly library data, which may be needed in order to import the '
    'dsbXML into older versions of DesignBuilder. However, this data can '
    'greatly increase the size of the resulting dsbXML file. Choose from '
    'the following options.', type=str, default='Default', show_default=True)
@click.option(
    '--program-name', '-p', help='Optional text to set the name of the '
    'software that will appear under under a comment in the XML to identify where '
    'it is being exported from. This can be set things like "Ladybug '
    'Tools" or "Pollination" or some other software in which this DsbXML '
    'export capability is being run. If unspecified, no comment will appear.',
    type=str, default=None, show_default=True)
@click.option(
    '--output-file', '-o', help='Optional dsbXML file path to output the dsbXML string '
    'of the translation. By default this will be printed out to stdout.',
    type=click.File('wb'), default='-', show_default=True)
def model_to_dsbxml_cli(model_file, xml_template, program_name, output_file):
    """Translate a Honeybee Model to an DsbXML file.

    \b
    Args:
        model_file: Full path to a Honeybee Model file (HBJSON or HBpkl).
    """
    try:
        model_to_dsbxml(model_file, xml_template, program_name, output_file)
    except Exception as e:
        _logger.exception(f'Model translation failed:\n{e}')
        sys.exit(1)
    else:
        sys.exit(0)


def model_to_dsbxml(
    model_file, xml_template='Default', program_name=None, output_file=None,
):
    """Translate a Honeybee Model to an DsbXML file.

    Args:
        model_file: Full path to a Honeybee Model file (HBJSON or HBpkl).
        xml_template: Text for the type of template file to be used to write the
            dsbXML. Different templates contain different amounts of default
            assembly library data, which may be needed in order to import the
            dsbXML into older versions of DesignBuilder. However, this data can
            greatly increase the size of the resulting dsbXML file. Choose from
            the following options.

            * Default - a minimal file that imports into the latest versions
            * Assembly - the Default plus an AssemblyLibrary with typical objects
            * Full - a large file with all libraries that can be imported to version 7.3

        program_name: Optional text to set the name of the software that will
            appear under a comment in the XML to identify where it is being exported
            from. This can be set things like "Ladybug Tools" or "Pollination"
            or some other software in which this DsbXML export capability is being
            run. If None, no comment will appear. (Default: None).
        output_file: Optional dsbXML file path to output the dsbXML string of the
            translation. If None, the string will be returned from this function.
    """
    # re-serialize the Model to Python
    model = Model.from_file(model_file)
    # create the DsbXML string for the model

    # write out the dsbXML file
    if isinstance(output_file, str):
        model_writer.model_to_dsbxml_file(
            model, output_file, xml_template=xml_template, program_name=program_name
        )
    else:
        dsbxml_str = model_writer.model_to_dsbxml(
            model, xml_template=xml_template, program_name=program_name)
        f_contents = dsbxml_str.encode('iso-8859-15')
        if output_file is None:
            b = base64.b64encode(f_contents)
            base64_string = b.decode('utf-8')
            return base64_string
        else:
            output_file.write(f_contents)
