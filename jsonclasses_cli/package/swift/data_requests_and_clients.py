from typing import cast
from inflection import camelize, underscore
from jsonclasses.cdef import Cdef
from jsonclasses_server.aconf import AConf
from .codable_class import CodableClassItem
from .shared_utils import class_create_input_items, class_include_items, class_update_input_items, list_query_items
from ...utils.join_lines import join_lines
from ...utils.package_utils import (
    class_needs_api, class_needs_session, to_create_input, to_create_request, to_delete_request,
    to_id_request, to_list_query, to_list_request, to_list_result, to_result_picks, to_single_query,
    to_update_input, to_result, to_update_request, to_sort_orders, to_include
)


def data_client_instances(cdef: Cdef) -> str:
    if not class_needs_api(cdef):
        return ''
    aconf = cast(AConf, cdef.cls.aconf)
    var_name = camelize(underscore(aconf.name), False)
    client_name = cdef.name + 'Client'
    return f'public var {var_name} = {client_name}()'


def data_requests_and_clients(cdef: Cdef) -> str:
    if not class_needs_api(cdef):
        return ''
    aconf = cast(AConf, cdef.cls.aconf)
    return join_lines([
        _data_create_request(cdef, aconf.name) if 'C' in aconf.actions else '',
        _data_update_request(cdef, aconf.name) if 'U' in aconf.actions else '',
        _data_delete_request(cdef, aconf.name) if 'D' in aconf.actions else '',
        _data_id_request(cdef, aconf.name) if 'R' in aconf.actions else '',
        _data_find_request(cdef, aconf.name) if 'L' in aconf.actions else '',
        _data_client(cdef, aconf)
    ], 2)


def _data_find_request_nums(cdef: Cdef, method_name: str) -> str:
    return f"""
    public mutating func {method_name}(_ {method_name}: Int) -> {to_list_request(cdef)} {'{'}
        if query == nil {'{'} query = {to_list_query(cdef)}() {'}'}
        query = query!.{method_name}({method_name})
        return self
    {'}'}

    public mutating func {method_name}(_ {method_name}: Int) async throws -> [{to_result(cdef)}] {'{'}
        self = self.{method_name}({method_name})
        return try await self.exec()
    {'}'}""".strip('\n')


def _data_find_request_method(cdef: Cdef) -> str:
    return f"""
    public mutating func order(_ order: {to_sort_orders(cdef)}) -> {to_list_request(cdef)} {'{'}
        if query == nil {'{'} query = {to_list_query(cdef)}() {'}'}
        query = query!.order(order)
        return self
    {'}'}

    public mutating func order(_ orders: [{to_sort_orders(cdef)}]) -> {to_list_request(cdef)} {'{'}
        if query == nil {'{'} query = {to_list_query(cdef)}() {'}'}
        query = query!.order(orders)
        return self
    {'}'}

    public mutating func order(_ order: {to_sort_orders(cdef)}) async throws -> [{to_result(cdef)}] {'{'}
        self = self.order(order)
        return try await self.exec()
    {'}'}

    public mutating func order(_ orders: [{to_sort_orders(cdef)}]) async throws -> [{to_result(cdef)}] {'{'}
        self = self.order(orders)
        return try await self.exec()
    {'}'}

{join_lines(map(lambda n: _data_find_request_nums(cdef, n), ['skip', 'limit', 'pageSize', 'pageNo']), 2)}
    """.strip('\n')


def _data_query_request_common(cdef: Cdef, single: bool = True) -> str:
    return join_lines([f"""
    public mutating func pick(_ picks: [{to_result_picks(cdef)}]) -> Self {'{'}
        if query == nil {'{'} query = {to_single_query(cdef) if single else to_list_query(cdef)}() {'}'}
        query = query!.pick(picks)
        return self
    {'}'}

    public mutating func pick(_ picks: [{to_result_picks(cdef)}]) async throws -> {to_result(cdef) if single else to_list_result(cdef)} {'{'}
        self = self.pick(picks)
        return try await self.exec()
    {'}'}

    public mutating func omit(_ omits: [{to_result_picks(cdef)}]) -> Self {'{'}
        if query == nil {'{'} query = {to_single_query(cdef) if single else to_list_query(cdef)}() {'}'}
        query = query!.omit(omits)
        return self
    {'}'}

    public mutating func omit(_ omits: [{to_result_picks(cdef)}]) async throws -> {to_result(cdef) if single else to_list_result(cdef)} {'{'}
        self = self.omit(omits)
        return try await self.exec()
    {'}'}""".strip('\n'), _data_query_request_includes(cdef, single)], 2)


def _data_query_request_include(cdef: Cdef, item: tuple[str, str], single: bool = True) -> str:
    return f"""
    public mutating func include(_ ref: {cdef.name}{camelize(item[0])}Include, _ query: {item[1]}? = nil) -> Self {'{'}
        if self.query == nil {'{'} self.query = {to_single_query(cdef) if single else to_list_query(cdef)}() {'}'}
        self.query = self.query!.include(ref, query)
        return self
    {'}'}

    public mutating func include(_ ref: {cdef.name}{camelize(item[0])}Include, _ query: {item[1]}? = nil) async throws -> {to_result(cdef) if single else to_list_result(cdef)} {'{'}
        if self.query == nil {'{'} self.query = {to_single_query(cdef) if single else to_list_query(cdef)}() {'}'}
        self.query = self.query!.include(ref, query)
        return try await self.exec()
    {'}'}
    """.strip('\n')


def _data_query_request_includes(cdef: Cdef, single: bool = True) -> str:
    items = class_include_items(cdef)
    if len(items) == 0:
        return ''
    return join_lines(map(lambda i: _data_query_request_include(cdef, i, single), items), 2)


def _data_create_request(cdef: Cdef, name: str) -> str:
    return join_lines([
        f"public struct {to_create_request(cdef)} {'{'}",
        f"    internal var input: {to_create_input(cdef)}",
        f"    internal var query: {to_single_query(cdef)}?",
        '\n',
        f"    internal func exec() async throws -> {to_result(cdef)} {'{'}",
        f"        return try await RequestManager.shared.post(",
        f'            url: "/{name}", input: input, query: query',
        f"        )",
        "    }",
        '\n',
        _data_query_request_common(cdef),
        '}'
    ], 1)


def _data_update_request(cdef: Cdef, name: str) -> str:
    return join_lines([
        f"public struct {to_update_request(cdef)} {'{'}",
        "    internal var id: String",
        f"    internal var input: {to_update_input(cdef)}",
        f"    internal var query: {to_single_query(cdef)}?",
        '\n',
        f"    internal func exec() async throws -> {to_result(cdef)} {'{'}",
        f"        return try await RequestManager.shared.patch(",
        f'            url: "/{name}/\(id)", input: input, query: query',
        f"        )",
        "    }",
        '\n',
        _data_query_request_common(cdef),
        '}'
    ], 1)


def _data_delete_request(cdef: Cdef, name: str) -> str:
    return join_lines([
        f"public struct {to_delete_request(cdef)} {'{'}",
        "    internal var id: String",
        "\n",
        "    internal func exec() async throws {",
        "        return try await RequestManager.shared.delete(",
        f'            url: "/{name}/\(id)"',
        "        )",
        "    }",
        "}"
    ], 1)


def _data_id_request(cdef: Cdef, name: str) -> str:
    return join_lines([
        f"public struct {to_id_request(cdef)} {'{'}",
        "    internal var id: String",
        f"    internal var query: {to_single_query(cdef)}?",
        '\n',
        f"    internal func exec() async throws -> {to_result(cdef)} {'{'}",
        f"        return try await RequestManager.shared.get(",
        f'            url: "/{name}/\(id)", query: query',
        f"        )!",
        "    }",
        '\n',
        _data_query_request_common(cdef),
        '}'
    ], 1)


def _data_find_request(cdef: Cdef, name: str) -> str:
    return join_lines([
        f"public struct {to_list_request(cdef)} {'{'}",
        f"    internal var query: {to_list_query(cdef)}?",
        '\n',
        f"    internal func exec() async throws -> [{to_result(cdef)}] {'{'}",
        f"        return try await RequestManager.shared.get(",
        f'            url: "/{name}", query: query',
        f"        )!",
        "    }",
        '\n',
        _data_find_request_method(cdef),
        _data_query_request_common(cdef, False),
        '}'
    ], 1)


def _data_client(cdef: Cdef, aconf: AConf) -> str:
    return join_lines([
        f'public struct {cdef.name}Client {"{"}',
        '\n',
        '    fileprivate init() { }',
        '\n',
        join_lines([
            _data_client_creates(cdef, aconf),
            _data_client_updates(cdef, aconf),
            _data_client_delete(cdef, aconf),
            _data_client_ids(cdef, aconf),
            _data_client_finds(cdef, aconf),
        ], 2),
        '}'
    ], 1)


def _data_client_create_2(cdef: Cdef, items: list[CodableClassItem]) -> str:
    if len(items) == 0:
        return join_lines([
            f'    public func create() -> {to_create_request(cdef)} {"{"}',
            f'        let input = {to_create_input(cdef)}()',
            '        return create(input)',
            '    }'
        ], 1)
    last = len(items) - 1
    return join_lines([
        f'    public func create(',
        *map(lambda i: f"        {i[1][2]}: {i[1][3]}{'? = nil' if i[1][4] else ''}{'' if i[0] == last else ', '}", enumerate(items)),
        f'    ) -> {to_create_request(cdef)} {"{"}',
        f'        let input = {to_create_input(cdef)}(',
        *map(lambda i: f"            {i[1][2]}: {i[1][2]}{'' if i[0] == last else ','}", enumerate(items)),
        '        )',
        '        return create(input)',
        '    }'
    ], 1)


def _data_client_create_4(cdef: Cdef, items: list[CodableClassItem]) -> str:
    if len(items) == 0:
        return join_lines([
            f'    public func create() async throws -> {to_result(cdef)} {"{"}',
            f'        let request: {to_create_request(cdef)} = self.create()',
            '        return try await request.exec()',
            '    }'
        ], 1)
    last = len(items) - 1
    return join_lines([
        f'    public func create(',
        *map(lambda i: f"        {i[1][2]}: {i[1][3]}{'? = nil' if i[1][4] else ''}{'' if i[0] == last else ', '}", enumerate(items)),
        f'    ) async throws -> {to_result(cdef)} {"{"}',
        f'        let request: {to_create_request(cdef)} = self.create(',
        *map(lambda i: f"            {i[1][2]}: {i[1][2]}{'' if i[0] == last else ','}", enumerate(items)),
        '        )',
        '        return try await request.exec()',
        '    }'
    ], 1)


def _data_client_creates(cdef: Cdef, aconf: AConf) -> str:
    if 'C' not in aconf.actions:
        return ''
    input_items = class_create_input_items(cdef)
    return join_lines([
        f'    public func create(_ input: {to_create_input(cdef)}) -> {to_create_request(cdef)} {"{"}',
        f'        return {to_create_request(cdef)}(input: input)',
        '    }',
        '\n',
        _data_client_create_2(cdef, input_items),
        '\n',
        f'    public func create(_ input: {to_create_input(cdef)}) async throws -> {to_result(cdef)} {"{"}',
        f'        let request: {to_create_request(cdef)} = self.create(input)',
        '        return try await request.exec()',
        '    }',
        '\n',
        _data_client_create_4(cdef, input_items)
    ], 1)


def _data_client_update_2(cdef: Cdef, items: list[CodableClassItem]) -> str:
    if len(items) == 0:
        return join_lines([
            f'    public func update(_ id: String) -> {to_update_request(cdef)} {"{"}',
            f'        let input = {to_update_input(cdef)}()',
            '        return update(id, input)',
            '    }'
        ], 1)
    last = len(items) - 1
    return join_lines([
        f'    public func update(',
        '        _ id: String,',
        *map(lambda i: f"        {i[1][2]}: {i[1][3]}{'? = nil' if i[1][4] else ''}{'' if i[0] == last else ', '}", enumerate(items)),
        f'    ) -> {to_update_request(cdef)} {"{"}',
        f'        let input = {to_update_input(cdef)}(',
        *map(lambda i: f"            {i[1][2]}: {i[1][2]}{'' if i[0] == last else ','}", enumerate(items)),
        '        )',
        '        return update(id, input)',
        '    }'
    ], 1)


def _data_client_update_4(cdef: Cdef, items: list[CodableClassItem]) -> str:
    if len(items) == 0:
        return join_lines([
            f'    public func update(_ id: String) async throws -> {to_result(cdef)} {"{"}',
            f'        let request: {to_update_request(cdef)} = self.update(id)',
            '        return try await request.exec()',
            '    }'
        ], 1)
    last = len(items) - 1
    return join_lines([
        f'    public func update(',
        '        _ id: String,',
        *map(lambda i: f"        {i[1][2]}: {i[1][3]}{'? = nil' if i[1][4] else ''}{'' if i[0] == last else ', '}", enumerate(items)),
        f'    ) async throws -> {to_result(cdef)} {"{"}',
        f'        let request: {to_update_request(cdef)} = self.update(',
        '            id,',
        *map(lambda i: f"            {i[1][2]}: {i[1][2]}{'' if i[0] == last else ','}", enumerate(items)),
        '        )',
        '        return try await request.exec()',
        '    }'
    ], 1)


def _data_client_updates(cdef: Cdef, aconf: AConf) -> str:
    if 'U' not in aconf.actions:
        return ''
    input_items = class_update_input_items(cdef)
    return join_lines([
        f'    public func update(_ id: String, _ input: {to_update_input(cdef)}) -> {to_update_request(cdef)} {"{"}',
        f'        return {to_update_request(cdef)}(id: id, input: input)',
        '    }',
        '\n',
        _data_client_update_2(cdef, input_items),
        '\n',
        f'    public func update(_ id: String, _ input: {to_update_input(cdef)}) async throws -> {to_result(cdef)} {"{"}',
        f'        let request: {to_update_request(cdef)} = self.update(id, input)',
        '        return try await request.exec()',
        '    }',
        '\n',
        _data_client_update_4(cdef, input_items)
    ], 1)


def _data_client_delete(cdef: Cdef, aconf: AConf) -> str:
    if 'D' not in aconf.actions:
        return ''
    return join_lines([
        '    public func delete(_ id: String) async throws {',
        f'        let request = {to_delete_request(cdef)}(id: id)',
        '        return try await request.exec()',
        '    }'
    ], 1)


def _data_client_ids(cdef: Cdef, aconf: AConf) -> str:
    if 'R' not in aconf.actions:
        return ''
    return f"""
    public func id(_ id: String) -> {to_id_request(cdef)} {'{'}
        return {to_id_request(cdef)}(id: id)
    {'}'}

    public func id(_ id: String) async throws -> {to_result(cdef)} {'{'}
        let request = {to_id_request(cdef)}(id: id)
        return try await request.exec()
    {'}'}
    """.strip('\n')


def _data_client_find_2(cdef: Cdef, items: list[tuple[str, str]]) -> str:
    last = len(items) - 1
    return join_lines([
        '    public func find(',
        *map(lambda i: f"        {i[1][0]}: {i[1][1]}? = nil{'' if i[0] == last else ','}", enumerate(items)),
        f'    ) -> {to_list_request(cdef)} {"{"}',
        f'        let query = {to_list_query(cdef)}(',
        *map(lambda i: f"            {i[1][0]}: {i[1][0]}{'' if i[0] == last else ','}", enumerate(items)),
        '        )',
        f'        return {to_list_request(cdef)}(query: query)',
        '    }'
    ], 1)


def _data_client_find_4(cdef: Cdef, items: list[tuple[str, str]]) -> str:
    last = len(items) - 1
    return join_lines([
        '    public func find(',
        *map(lambda i: f"        {i[1][0]}: {i[1][1]}? = nil{'' if i[0] == last else ','}", enumerate(items)),
        f'    ) async throws -> {to_list_result(cdef)} {"{"}',
        f'        let query = {to_list_query(cdef)}(',
        *map(lambda i: f"            {i[1][0]}: {i[1][0]}{'' if i[0] == last else ','}", enumerate(items)),
        '        )',
        f'        let request = {to_list_request(cdef)}(query: query)',
        '        return try await request.exec()',
        '    }'
    ], 1)


def _data_client_finds(cdef: Cdef, aconf: AConf) -> str:
    if 'L' not in aconf.actions:
        return ''
    query_items = list_query_items(cdef)
    return join_lines([
        f'    public func find(_ query: {to_list_query(cdef)}? = nil) -> {to_list_request(cdef)} {"{"}',
        f'        return {to_list_request(cdef)}(query: query)',
        '    }',
        '\n',
        _data_client_find_2(cdef, query_items),
        '\n',
        f'    public func find(_ query: {to_list_query(cdef)}? = nil) async throws -> {to_list_result(cdef)} {"{"}',
        f'        let request = {to_list_request(cdef)}(query: query)',
        '        return try await request.exec()',
        '    }',
        '\n',
        _data_client_find_4(cdef, query_items)
    ], 1)
