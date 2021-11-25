from inflection import camelize
from jsonclasses.cdef import Cdef
from jsonclasses.fdef import FType
from .unary_sort_order import unary_sort_order
from .codable_struct import codable_struct, codable_struct_item
from .codable_enum import codable_associated_item, codable_enum, codable_enum_item
from .codable_class import codable_class, codable_class_item
from .jtype_to_swift_type import jtype_to_swift_type
from .shared_utils import (
    class_create_input_items, class_update_input_items, is_field_nonnull,
    is_field_primary, is_field_local_key, field_can_read, field_can_create,
    field_can_update, field_has_default, field_ref_id_name, is_field_queryable,
    is_field_ref, is_field_required_for_create, is_field_required_for_read,
    array, list_query_items
)
from ...utils.join_lines import join_lines
from ...utils.package_utils import (
    to_create_input, to_update_input, to_single_query, to_list_query, to_result,
    to_result_picks, to_include, to_sort_orders
)


def data_class(cdef: Cdef) -> str:
    return join_lines([
        _class_create_input(cdef),
        _class_update_input(cdef),
        _class_sort_orders(cdef),
        _class_result_picks(cdef),
        _class_include_key_enums(cdef),
        _class_include_enum(cdef),
        _class_single_query(cdef),
        _class_list_query(cdef),
        _class_result(cdef),
    ], 2)


def _class_create_input(cdef: Cdef) -> str:
    return codable_class(to_create_input(cdef), class_create_input_items(cdef))


def _class_update_input(cdef: Cdef) -> str:
    return codable_class(to_update_input(cdef), class_update_input_items(cdef))


def _class_sort_orders(cdef: Cdef) -> str:
    fnames: list[str] = []
    for field in cdef.fields:
        if not is_field_queryable(field):
            continue
        if is_field_primary(field):
            continue
        if is_field_ref(field):
            continue
        if not field_can_read(field):
            continue
        fnames.append(camelize(field.name, False))
    enum_items: list[str] = []
    for name in fnames:
        enum_items.append(codable_enum_item(name, 'String', name))
        desc_name = name + 'Desc'
        enum_items.append(codable_enum_item(desc_name, 'String', "-" + name))
    name = to_sort_orders(cdef)
    enum = codable_enum(name, 'String', enum_items)
    unary = unary_sort_order(name)
    return join_lines([enum, unary], 2)


def _class_result_picks(cdef: Cdef) -> str:
    items: list[str] = []
    for field in cdef.fields:
        if not field_can_read(field):
            continue
        name = camelize(field.name, False)
        items.append(codable_enum_item(name, 'String', name))
        if is_field_local_key(field):
            idname = field_ref_id_name(field)
            items.append(codable_enum_item(idname, 'String', idname))
    return codable_enum(to_result_picks(cdef), 'String', items)


def _class_include_items(cdef: Cdef) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for field in cdef.fields:
        if is_field_ref(field):
            if field.fdef.ftype == FType.LIST:
                items.append((field.name, to_list_query(field.foreign_cdef)))
            else:
                items.append((field.name, to_single_query(field.foreign_cdef)))
    return items


def _class_include_key_enums(cdef: Cdef) -> str:
    cname = cdef.name
    enums: list[str] = []
    for field in cdef.fields:
        if is_field_ref(field):
            enums.append(_class_include_key_enum(cname, field.name))
    return join_lines(enums, 2)


def _class_include_key_enum(cname: str, fname: str) -> str:
    return codable_enum(cname + camelize(fname) + 'Include', 'Int', [
        codable_enum_item(fname, 'Int', '1')
    ])


def _class_include_enum_init_if(idx: int, key: str, q: str) -> str:
    return f"""
        {'} else ' if idx > 0 else ''}if container.contains(.{key}) {'{'}
            self = .{key}(try! container.decode({q}.self, forKey: .{key}))""".strip('\n')


def _class_include_enum_encode_case(key: str) -> str:
    return f"""
        case .{key}(let value):
            try! container.encode(value, forKey: .{key})""".strip('\n')


def _class_include_enum(cdef: Cdef) -> str:
    items = _class_include_items(cdef)
    if len(items) == 0:
        return ""
    cases = join_lines(map(lambda i: codable_associated_item(i[0], i[1] + '?'), items), 1)
    coding_keys = join_lines([
        '    enum CodingKeys: String, CodingKey {',
        *map(lambda i: f'        case {i[0]} = "{i[0]}"', items),
        '    }'
    ], 1)
    init = join_lines([
        '    public init(from decoder: Decoder) throws {',
        '        let container = try! decoder.container(keyedBy: CodingKeys.self)',
        join_lines(map(lambda t: _class_include_enum_init_if(t[0], t[1][0], t[1][1]), enumerate(items))),
        '        } else {',
        '            throw NSError()',
        '        }',
        '    }'
    ], 1)
    encode = join_lines([
        '    public func encode(to encoder: Encoder) throws {',
        '        var container = encoder.container(keyedBy: CodingKeys.self)',
        '        switch self {',
        join_lines(map(lambda t: _class_include_enum_encode_case(t[0]), items)),
        '        }',
        '    }'
    ])
    return codable_enum(to_include(cdef), None, [join_lines([
        cases,
        coding_keys,
        init,
        encode
    ], 2)])


def _single_query_items(cdef: Cdef) -> list[str]:
    result_picks = array(to_result_picks(cdef))
    result_includes = array(to_include(cdef))
    pick = codable_struct_item(
        'fileprivate', 'var', '_pick', result_picks, True, 'nil')
    omit = codable_struct_item(
        'fileprivate', 'var', '_omit', result_picks, True, 'nil')
    includes = codable_struct_item(
        'fileprivate', 'var', '_includes', result_includes, True, 'nil')
    if len(_class_include_items(cdef)) == 0:
        includes = ""
    return [pick, omit, includes]


def _single_query_picks_omits(cdef: Cdef) -> str:
    rpname = to_result_picks(cdef)
    return f"""
    public static func pick(_ picks: [{rpname}]) -> Self {'{'}
        return Self(_pick: picks)
    {'}'}

    public mutating func pick(_ picks: [{rpname}]) -> Self {'{'}
        _pick = picks
        return self
    {'}'}

    public static func omit(_ omits: [{rpname}]) -> Self {'{'}
        return Self(_omit: omits)
    {'}'}

    public mutating func omit(_ omits: [{rpname}]) -> Self {'{'}
        _omit = omits
        return self
    {'}'}""".strip('\n')


def _single_query_include(key: str, itype: str, qtype: str) -> str:
    return f"""
    public static func include(_ ref: {itype}, query: {qtype}? = nil) -> Self {'{'}
        return Self(_includes: [.{key}(query)])
    {'}'}

    public mutating func include(_ ref: {itype}, query: {qtype}? = nil) -> Self {'{'}
        if _includes == nil {'{'} _includes = [] {'}'}
        _includes!.append(.{key}(query))
        return self
    {'}'}""".strip('\n')


def _single_query_includes(cdef: Cdef) -> str:
    items: list[tuple(str, str, str)] = []
    for field in cdef.fields:
        if is_field_ref(field):
            if field.fdef.ftype == FType.LIST:
                items.append((field.name, cdef.name + camelize(field.name) + 'Include', to_list_query(field.foreign_cdef)))
            else:
                items.append((field.name, cdef.name + camelize(field.name) + 'Include', to_single_query(field.foreign_cdef)))
    return join_lines(map(lambda i: _single_query_include(i[0], i[1], i[2]), items), 2)


def _list_query_orders(order: str) -> str:
    return f"""
    public static func order(_ order: {order}) -> Self {"{"}
       return Self(_order: [order])
    {"}"}

    public static func order(_ orders: [{order}]) -> Self {"{"}
        return Self(_order: orders)
    {"}"}

    public mutating func order(_ order: {order}) -> Self {"{"}
        if _order == nil {"{"} _order = [] {"}"}
        _order!.append(order)
        return self
    {"}"}

    public mutating func order(_ orders: [{order}]) -> Self {"{"}
        if _order == nil {"{"} _order = [] {"}"}
        _order!.append(contentsOf: orders)
        return self
    {"}"}"""


def _list_query_limit_skip_pn_ps() -> str:
    lspp = ["limit", "skip", "pageNo", "pageSize"]
    reslut = []
    for i in lspp:
        reslut.append(f"""
    public static func {i}(_ {i}: Int) -> Self {"{"}
        return Self(_{i}: {i})
    {"}"}

    public mutating func {i}(_ {i}: Int) -> Self {"{"}
        _{i} = {i}
        return self
    {"}"}""".strip('\n'))
    return join_lines(reslut)

def _class_single_query(cdef: Cdef) -> str:
    return codable_struct(to_single_query(cdef), [join_lines([
        join_lines(_single_query_items(cdef), 1),
        _single_query_picks_omits(cdef),
        _single_query_includes(cdef)
    ], 2)])


def _list_query_find(cdef: Cdef) -> str:
    items = list_query_items(cdef)
    last = len(items) - 1
    arglist = lambda i: f"        {i[1][0]}: {i[1][1]}? = nil{'' if i[0] == last else ','}"
    return join_lines([
        '    public static func `where`(',
        *map(arglist, enumerate(items)),
        '    ) -> Self {',
        '        return Self(',
        *map(lambda i: f"        {i[1][0]}: {i[1][0]}{'' if i[0] == last else ','}", enumerate(items)),
        '        )',
        '    }',
        '\n',
        '    public mutating func `where`(',
        *map(arglist, enumerate(items)),
        '    ) -> Self {',
        *map(lambda i: f"        if {i[0]} != nil {'{'} self.{i[0]} = {i[0]} {'}'}", items),
        '        return self',
        '    }'
    ], 1)


def _class_list_query(cdef: Cdef) -> str:
    items = list(map(lambda i: codable_struct_item('public', 'var', i[0], i[1], True, 'nil'), list_query_items(cdef)))
    sort_order = to_sort_orders(cdef)
    sort_orders = array(sort_order)
    order = codable_struct_item(
        'fileprivate', 'var', '_order', sort_orders, True, 'nil')
    limit = codable_struct_item(
        'fileprivate', 'var', '_limit', 'Int', True, 'nil')
    skip = codable_struct_item(
        'fileprivate', 'var', '_skip', 'Int', True, 'nil')
    page_no = codable_struct_item(
        'fileprivate', 'var', '_pageNo', 'Int', True, 'nil')
    page_size = codable_struct_item(
        'fileprivate', 'var', '_pageSize', 'Int', True, 'nil')
    operators = [
        order, limit, skip, page_no, page_size, *_single_query_items(cdef),
        '\n',
        join_lines([
            _list_query_find(cdef),
            _list_query_orders(sort_order),
            _list_query_limit_skip_pn_ps(),
            _single_query_picks_omits(cdef),
            _single_query_includes(cdef)
        ], 2)
    ]
    items.extend(operators)
    return codable_struct(to_list_query(cdef), items)


def _class_result(cdef: Cdef) -> str:
    items: list[str] = []
    for field in cdef.fields:
        if not field_can_read(field):
            continue
        optional = not is_field_required_for_read(field)
        name = camelize(field.name, False)
        stype = jtype_to_swift_type(field.fdef, 'R')
        local_key = is_field_local_key(field)
        item = codable_class_item('public', 'let', name, stype, optional)
        items.append(item)
        if local_key:
            idname = field_ref_id_name(field)
            item = codable_class_item('public', 'let', idname, 'String', optional)
            items.append(item)
    name = to_result(cdef)
    return codable_class(name, items, True)
