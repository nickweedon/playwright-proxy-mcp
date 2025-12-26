# Generated from grammar/AriaKey.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .AriaKeyParser import AriaKeyParser
else:
    from AriaKeyParser import AriaKeyParser

# This class defines a complete generic visitor for a parse tree produced by AriaKeyParser.

class AriaKeyVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by AriaKeyParser#key.
    def visitKey(self, ctx:AriaKeyParser.KeyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by AriaKeyParser#role.
    def visitRole(self, ctx:AriaKeyParser.RoleContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by AriaKeyParser#name.
    def visitName(self, ctx:AriaKeyParser.NameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by AriaKeyParser#attributes.
    def visitAttributes(self, ctx:AriaKeyParser.AttributesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by AriaKeyParser#attribute.
    def visitAttribute(self, ctx:AriaKeyParser.AttributeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by AriaKeyParser#attrName.
    def visitAttrName(self, ctx:AriaKeyParser.AttrNameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by AriaKeyParser#attrValue.
    def visitAttrValue(self, ctx:AriaKeyParser.AttrValueContext):
        return self.visitChildren(ctx)



del AriaKeyParser