import lex

class Node:
    pass

class ConstNode(Node):
    def __init__(self, first_type_token, type, name, value):
        Node.__init__(self)
        self.first_type_token = first_type_token
        self.type = type
        self.name = name
        self.value = value
    def getToken(self):
        return self.first_type_token

class TypedefNode(Node):
    def __init__(self, typedef_token, name, def_type):
        Node.__init__(self)
        self.typedef_token = typedef_token
        self.name = name
        self.def_type = def_type
    def getToken(self):
        return self.typedef_token

class StructNode(Node):
    def __init__(self, struct_token, name, fields):
        Node.__init__(self)
        self.struct_token = struct_token
        self.name = name
        self.fields = fields
    def getToken(self):
        return self.struct_token

class FieldNode(Node):
    def __init__(self, first_type_token, type, name):
        Node.__init__(self)
        self.first_type_token = first_type_token
        self.type = type
        self.name = name
    def getToken(self):
        return self.first_type_token

class FuncNode(Node):
    def __init__(self, first_type_token, name, return_type, args):
        Node.__init__(self)
        self.first_type_token = first_type_token
        self.name = name
        self.return_type = return_type
        self.args = args
    def getToken(self):
        return self.first_type_token

class ArgNode(Node):
    def __init__(self, type, name_token, name):
        Node.__init__(self)
        self.type = type
        self.name_token = name_token
        self.name = name
    def getToken(self):
        return self.name_token

class Type:
    pass
class NamedType(Type):
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return self.name
class SinglePtrType(Type):
    def __init__(self, sub_type, const):
        self.sub_type = sub_type
        self.const = const
    def __repr__(self):
        return "{}{}*".format("const " if self.const else "", self.sub_type)
class ArrayPtrType(Type):
    def __init__(self, sub_type, const):
        self.sub_type = sub_type
        self.const = const
    def __repr__(self):
        return "{}{}[]".format("const " if self.const else "", self.sub_type)

class Parser:
    def __init__(self, lexer: lex.Lexer):
        self.lexer = lexer
        self.lookahead = []
        self.str = lexer.reader.str

    def peekToken(self):
        if not self.lookahead:
            self.lookahead.append(self.lexer.lexToken())
        return self.lookahead[0]

    def popToken(self):
        assert(self.lookahead)
        self.lookahead.pop(0)

    def peekPopKnownToken(self, context, kinds):
        token = self.peekToken()
        if not token.kind in kinds:
            expected = kinds[0] if len(kinds) == 1 else "one of {}".format(", ".join(kinds))
            self.errAt(token, "expected {} {} but got {}".format(expected, context, token.desc(self.str)))
        self.popToken()
        return token

    def errAt(self, token, msg):
        self.lexer.errAt(token.start, msg)

    def parseInto(self, nodes):
        while True:
            node = self.parseDefinition()
            if not node:
                break
            nodes.append(node)

    def parseDefinition(self):
        first_token = self.peekToken()
        #print("[DEBUG] parseExpressionPart token={}".format(first_token.desc(self.str)))
        if first_token.kind == lex.EOF:
            self.popToken()
            return None
        if first_token.kind == lex.ID:
            id = self.str[first_token.start:first_token.end]
            if id == "typedef":
                self.popToken()
                return self.parseTypedef(first_token)
            if id == "struct":
                self.popToken()
                return self.parseStruct(first_token)

        #
        # must be a function or constant
        #
        type = self.parseType()
        name_token = self.peekPopKnownToken("after 'TYPE' (could be function or const)", (lex.ID,))
        punctuation_token = self.peekToken()
        if punctuation_token.kind == lex.EQUAL:
            self.popToken()
            value = self.parseConstValue()
            _ = self.peekPopKnownToken("to finish const", (lex.SEMICOLON,))
            return ConstNode(first_token, type, self.str[name_token.start:name_token.end], value)
        if punctuation_token.kind == lex.LEFT_PAREN:
            self.popToken()
            return self.parseFunc(first_token, type, name_token)

        self.errAt(first_token, "expected '=' or '(' after 'TYPE ID' but got {}".format(punctuation_token.desc(self.str)))

    def parseConstValue(self):
        token = self.peekToken()
        if token.kind == lex.DASH:
            self.popToken()
            return "-" + self.parseConstValue()
        if token.kind == lex.NUMBER:
            self.popToken()
            return token.value
        self.errAt(token, "expected a constant value but got {}".format(token.desc(self.str)))

    def parseTypedef(self, typedef_token):
        def_type = self.parseType()
        name_token = self.peekPopKnownToken("after 'typedef TYPE'", (lex.ID,))
        _ = self.peekPopKnownToken("to finish typedef", (lex.SEMICOLON,))
        return TypedefNode(typedef_token, self.str[name_token.start:name_token.end], def_type)

    def parseType(self):
        const = False
        token = self.peekToken()
        if token.kind != lex.ID:
            self.errAt(token, "expected type to start with ID but got: {}".format(token.desc(self.str)))
        token_str = self.str[token.start:token.end]
        if token_str == "const":
            const = True
            self.popToken()
            token = self.peekToken()
            if token.kind != lex.ID:
                self.errAt(token, "expected ID after 'const' but got {}".format(token.desc(self.str)))
            token_str = self.str[token.start:token.end]
        type = NamedType(token_str)
        self.popToken()
        while True:
            mod_token = self.peekToken()
            if mod_token.kind == lex.STAR:
                type = SinglePtrType(type, const)
                self.popToken()
            elif mod_token.kind == lex.LEFT_BRACKET:
                self.popToken()
                _ = self.peekPopKnownToken("to finish array type", (lex.RIGHT_BRACKET,))
                type = ArrayPtrType(type, const)
            else:
                break
        return type

    def parseStruct(self, struct_token):
        struct_name_token = self.peekPopKnownToken("after 'struct'", (lex.ID,))
        _ = self.peekPopKnownToken("after 'struct ID'", (lex.LEFT_CURLY,))
        fields = []
        while True:
            next_token = self.peekToken()
            if next_token.kind == lex.EOF:
                self.errAt(next_token, "expected a struct field but got EOF")
            if next_token.kind == lex.RIGHT_CURLY:
                self.popToken()
                break
            field_type_token = self.peekToken()
            field_type = self.parseType()
            field_name_token = self.peekPopKnownToken("after field type", (lex.ID,))
            _ = self.peekPopKnownToken("to finish field declaration", (lex.SEMICOLON,))
            fields.append(FieldNode(field_type_token, field_type, self.str[field_name_token.start:field_name_token.end]))

        return StructNode(struct_token, self.str[struct_name_token.start:struct_name_token.end], fields)

    def parseFunc(self, first_token, return_type, func_name_token):
        args = []
        while True:
            next_token = self.peekToken()
            if next_token.kind == lex.EOF:
                self.errAt(next_token, "expected a function argument or ) but got EOF")
            if next_token.kind == lex.RIGHT_PAREN:
                self.popToken()
                break
            arg_type = self.parseType()
            arg_name_token = self.peekPopKnownToken("after argument type", (lex.ID,))
            maybe_comma_token = self.peekToken()
            if maybe_comma_token.kind == lex.COMMA:
                self.popToken()
            elif maybe_comma_token.kind != lex.RIGHT_PAREN:
                self.errAt(maybe_comma_token, "expected , or ) to finish function arguments but got {}".format(maybe_comma_token.desc(self.str)))
            args.append(ArgNode(arg_type, arg_name_token, self.str[arg_name_token.start:arg_name_token.end]))
        _ = self.peekPopKnownToken("to finish function declaration", (lex.SEMICOLON,))

        return FuncNode(first_token, self.str[func_name_token.start:func_name_token.end], return_type, args)