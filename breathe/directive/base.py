
from breathe.renderer.rst.doxygen.base import RenderContext
from breathe.renderer.rst.doxygen import format_parser_error
from breathe.parser import ParserError, FileIOError
from breathe.project import ProjectError
from breathe.finder.core import NoMatchesError

from docutils.parsers import rst
from docutils.parsers.rst.directives import unchanged_required, flag
from docutils import nodes

class WarningHandler(object):

    def __init__(self, state, context):
        self.state = state
        self.context = context

    def warn(self, text):
        result = text.format(**self.context)
        return [
            nodes.warning("", nodes.paragraph("", "", nodes.Text(result))),
            self.state.document.reporter.warning(result, line=self.context['lineno'])
            ]


def create_warning(project_info, state, lineno, **kwargs):

    tail = ''
    if project_info:
        tail = 'in doxygen xml output for project "{project}" from directory: {path}'.format(
            project=project_info.name(),
            path=project_info.project_path()
            )

    context = dict(
        lineno=lineno,
        tail=tail,
        **kwargs
        )

    return WarningHandler(state, context)


class BaseDirective(rst.Directive):

    def __init__(self, root_data_object, renderer_factory_creator_constructor, finder_factory,
                 matcher_factory, project_info_factory, filter_factory, target_handler_factory,
                 *args):
        rst.Directive.__init__(self, *args)

        self.root_data_object = root_data_object
        self.renderer_factory_creator_constructor = renderer_factory_creator_constructor
        self.finder_factory = finder_factory
        self.matcher_factory = matcher_factory
        self.project_info_factory = project_info_factory
        self.filter_factory = filter_factory
        self.target_handler_factory = target_handler_factory

    def render(self, data_object, project_info, filter_, target_handler):
        "Standard render process used by subclasses"

        renderer_factory_creator = self.renderer_factory_creator_constructor.create_factory_creator(
            project_info,
            self.state.document,
            self.options,
            target_handler
            )

        try:
            renderer_factory = renderer_factory_creator.create_factory(
                data_object,
                self.state,
                self.state.document,
                filter_,
                target_handler,
                )
        except ParserError, e:
            return format_parser_error("doxygenclass", e.error, e.filename, self.state,
                                       self.lineno, True)
        except FileIOError, e:
            return format_parser_error("doxygenclass", e.error, e.filename, self.state, self.lineno)

        context = RenderContext([data_object, self.root_data_object])
        object_renderer = renderer_factory.create_renderer(context)
        node_list = object_renderer.render()

        return node_list


class DoxygenBaseDirective(BaseDirective):

    required_arguments = 1
    optional_arguments = 1
    option_spec = {
        "path": unchanged_required,
        "project": unchanged_required,
        "outline": flag,
        "no-link": flag,
        }
    has_content = False

    def run(self):

        try:
            namespace, name = self.arguments[0].rsplit("::", 1)
        except ValueError:
            namespace, name = "", self.arguments[0]

        try:
            project_info = self.project_info_factory.create_project_info(self.options)
        except ProjectError, e:
            warning = create_warning(None, self.state, self.lineno)
            return warning.warn('doxygen%s: %s' % (self.kind, e))

        finder = self.finder_factory.create_finder(project_info)

        matcher_stack = self.create_matcher_stack(namespace, name)

        try:
            data_object = finder.find_one(matcher_stack)
        except NoMatchesError, e:
            display_name = "%s::%s" % (namespace, name) if namespace else name
            warning = create_warning(project_info, self.state, self.lineno, name=display_name,
                                     kind=self.kind)
            return warning.warn('doxygen{kind}: Cannot find {kind} "{name}" {tail}')

        target_handler = self.target_handler_factory.create_target_handler(
            self.options, project_info, self.state.document)
        filter_ = self.filter_factory.create_outline_filter(self.options)

        return self.render(data_object, project_info, filter_, target_handler)

