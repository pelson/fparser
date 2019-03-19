from fparser.two.parser import ParserFactory
from fparser.common.readfortran import FortranStringReader
import sys

import path_matcher

with open(sys.argv[1], 'r') as fh:
    code = fh.read()

parser = ParserFactory().create(std="f2008")
program = parser(FortranStringReader(code))


def children(node):
    """Get the immediate children of the given node."""
    children = getattr(node, 'content', None)
    if children is None:
        children = getattr(node, 'items', None)
    return children


class Visitor:
    def __init__(self, program):
        self.visit(program)

    def find_visitor_method(self, node):
        for cls in type(node).mro():
            method = getattr(self, f'visit_{cls.__name__}', None)
            if method:
                break
        return method

    def visit(self, node, **kwargs):
        method = self.find_visitor_method(node)
        method(node, **kwargs)

    def visit_object(self, node, **kwargs):
        # This is the "fallback"/"generic" implementation that will be
        # called if there are no more specific visitor methods.
        for child in children(node) or []:
            self.visit(child, **kwargs)


class _PathBase:
    def __init__(self, node, children=None):
        self.node = node
        self.children = children or []

    @property
    def typename(self):
        return type(self.node).__name__

    def ancestors(self):
        """
        Generator of this node's ancestors, all the way to the root.

        At the root an empty iterator is returned.

        """
        return iter([])

    def path(self, root=None):
        path = '/'
        if root is not self:
            path = path + self.typename
        return path

    def decendants(self):
        """
        Walk through all of the decendants of this node.

        The generator returned can be told whether or not to decend
        into the children of the currently yielded node.

        >>> decendants = self.decendants()
        >>> for node in decendants:
        ...     print(node)
        ...     if 'Subroutine' in node.typename:
        ...         # We don't want the children of this node.
        ...         decendants.send(False)

        """
        for child in self.children:
            # Allow the generator to recieve communication regarding
            # whether to decend this child's children.
            prune = yield child
            if not prune:
                # NOTE: The pruning wont work here.
                for sub in child.decendants():
                    yield sub

    def __str__(self):
        return self.path()

    def __repr__(self):
        return '< Node of type {!r} >'.format(self.typename)

    def find_in(self, nodes, pattern):
        # Cast everything to a Path_Pattern (strings and lists
        # in particular).
        pattern = path_matcher.PathPattern.create_from(pattern)

        for node in nodes:
            if pattern.matches(node.path(root=self)):
                yield node

    def find_one_in(self, nodes, pattern):
        matches = list(self.find_in(nodes, pattern))
        if len(matches) == 0:
            raise ValueError('Pattern {!r} not found'.format(pattern))
        elif len(matches) > 1:
            raise ValueError(
                'Pattern {!r} found {} times, expecting '
                'only one.'.format(pattern, len(matches)))
        return matches[0]

    def find_children(self, pattern):
        return self.find_in(self.children, pattern)

    def find_child(self, pattern):
        return self.find_one_in(self.children, pattern)

    def find_decendants(self, pattern):
        return self.find_in(self.decendants(), pattern)

    def find_decendant(self, pattern):
        return self.find_one_in(self.decendants(), pattern)


class PathNode(_PathBase):
    def __init__(self, node, parent, children=None):
        self.parent = parent
        super().__init__(node, children=children)

    def path(self, root=None):
        path = super().path(root=root)
        if root is not self.parent:
            path = self.parent.path(root=root) + path
        return path

    def root(self):
        """
        Return the root node of the graph.

        """
        # There are many ways of skinning this one, but getting the last
        # ancestor is as good as any.
        # Ref: https://stackoverflow.com/questions/2138873
        ancestors = self.ancestors()
        last = next(ancestors)
        for last in iterator:
            continue
        return last

    def ancestors(self):
        yield self.parent
        if not isinstance(self.parent, PathRoot):
            # Recursively fetch the parent.
            for ancestor in self.parent.ancestors():
                yield ancestor


class PathRoot(_PathBase):
    pass


from collections import defaultdict
import six
class PathBuilder(Visitor):
    def visit_object(self, node, **kwargs):
        if 'parent' not in kwargs:
            result = PathRoot(node)
            self.root = result
        else:
            result = PathNode(node, kwargs['parent'])
            kwargs['parent'].children.append(result)
        kwargs['parent'] = result
        super().visit_object(node, **kwargs)

r = PathBuilder(program).root


def dump_line_info(root):
    line_number = 0
    for node in reversed(list(root.ancestors())):
        line = getattr(node.node, 'item', None)
        if line:
            line_number = line.span[0]
    if line_number != 0:
        print(line_number)

    for node in root.decendants():
        line = getattr(node.node, 'item', None)
        if line:
            if line_number != line.span[0]:
                line_number = line.span[0]
                print(line_number)
        print(node.path())

dump_line_info(r)
print(r)
for node in r.children:
    print(r)
print(r.children)

print(r.find_child('Module'))


def datatype_desc(data_component):
    data_name = data_component.find_decendant(['/Component_Decl/Name', '/Proc_Decl/Name']).node

    is_array = bool(list(
        data_component.find_decendants(['/Component_Decl/Deferred_Shape_Spec'])))

    # Find exactly one of...
    if str(data_component.typename) == 'Proc_Component_Def_Stmt':
        component_type = data_component.find_decendant('/Name')
        return '{} : procedure <<pointer>>'.format(data_name)
    else:
        component_type = data_component.find_decendant(
            ['/Declaration_Type_Spec/Type_Name',
             '/Intrinsic_Type_Spec/str',
            ])

        if component_type.typename == 'Intrinsic_Type_Spec':
            pass

        type_str = str(component_type.node).lower()
        if is_array:
            type_str = type_str + '[]'

        return '{} : {}'.format(data_name, type_str)


lines = []
for mod in r.find_decendants('Module'):
    for f in r.find_decendants('Module_Stmt/Name'):
        print(f, f.node)

    procedures = {}
    functions = {}
    for func in mod.find_decendants('/Module_Subprogram_Part/Function_Subprogram/Function_Stmt'):
        print('----------')
        print('FOO')
        dump_line_info(func)
        # Possible to have multiple names, e.g. "func_name(arg_name)"
        func_name = str(next(func.find_decendants('/Name')).node)

        assert func_name not in procedures
        functions[func_name] = func

    for proc in mod.find_decendants('/Module_Subprogram_Part/Subroutine_Subprogram/Subroutine_Stmt'):
        # Possible to have multiple names, e.g. "func_name(arg_name)"
        proc_name = str(next(proc.find_decendants('/Name')).node)
        procedures[proc_name] = proc

    print('FUNCS:', procedures.keys())
    print(functions.keys())

    mod_name = mod.find_decendant('/Module_Stmt/Name')
    for type_def in mod.find_decendants('Derived_Type_Def'):
        #for name in type_def.find_decendants('*/Type_Name'):
        #for name in type_def.find_decendants('/Derived_Type_Stmt/Type_Name'):
            #print(name)
            #print(name.path(root=type_def))

        name = type_def.find_decendant('/Derived_Type_Stmt/Type_Name')
        lines.append('class {}::{} {{'.format(mod_name.node, name.node))
        print(name.node)

        for data_component in type_def.find_decendants([
            '/Component_Part/Data_Component_Def_Stmt',
            '/Component_Part/Proc_Component_Def_Stmt',
            ]):
            private_or_public = '-'
            access_spec = data_component.find_decendants(['Access_Spec'])
            for spec in access_spec:
                if str(spec.node).lower() == 'public':
                    private_or_public = '+'

            lines.append(' {}{}'.format(private_or_public, datatype_desc(data_component)))

            for spec in data_component.find_decendants('Component_Attr_Spec'):
                if str(spec.node) == 'POINTER':
                    lines[-1] += ' <<pointer>>'
      
        lines.append('')
        for type_bound_procedure in type_def.find_decendants('/Type_Bound_Procedure_Part/Specific_Binding'):
            name = str(type_bound_procedure.find_child('Name').node)
            return_info = ''
            proc = procedures.get(name, None)
            func = functions.get(name, None)

            routine = proc or func
            print('-------------==============')
            print(name)
            variables = {}
            args = []
            if routine is not None:
                for type_decl in routine.parent.find_decendants('Specification_Part/Type_Declaration_Stmt'):
                    # We can have multiple variables of a particular type.
                    for var in type_decl.find_decendants('/Entity_Decl/Name'):
                        component_type = type_decl.find_decendant(
                            ['/Declaration_Type_Spec/Type_Name',
                             '/Intrinsic_Type_Spec/str',
                            ])
                        type_str = str(component_type.node).lower()
                        variables[str(var.node)] = type_str

                print(variables.keys())

                for arg in routine.find_decendants('/Dummy_Arg_List/Name'):
                    if not str(arg.node) == 'self':
                        if str(arg.node) in variables:
                            args.append('{} : {}'.format(arg.node, variables[str(arg.node)]))
                        else:
                            args.append(str(arg.node))

            if proc is None:
                return_info = 'func'
            if return_info:
                return_info = ' : ' + return_info
            if args:
                args = ' ' + ', '.join(args) + ' '
            else:
                args = ''
            lines.append(' +{}({}){}'.format(name, args, return_info))
         
        lines.append('}')
        lines.append('')

print('\n'.join(lines))
