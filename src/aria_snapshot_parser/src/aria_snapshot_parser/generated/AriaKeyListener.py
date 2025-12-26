# Generated from grammar/AriaKey.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .AriaKeyParser import AriaKeyParser
else:
    from AriaKeyParser import AriaKeyParser

# This class defines a complete listener for a parse tree produced by AriaKeyParser.
class AriaKeyListener(ParseTreeListener):

    # Enter a parse tree produced by AriaKeyParser#key.
    def enterKey(self, ctx:AriaKeyParser.KeyContext):
        pass

    # Exit a parse tree produced by AriaKeyParser#key.
    def exitKey(self, ctx:AriaKeyParser.KeyContext):
        pass


    # Enter a parse tree produced by AriaKeyParser#role.
    def enterRole(self, ctx:AriaKeyParser.RoleContext):
        pass

    # Exit a parse tree produced by AriaKeyParser#role.
    def exitRole(self, ctx:AriaKeyParser.RoleContext):
        pass


    # Enter a parse tree produced by AriaKeyParser#name.
    def enterName(self, ctx:AriaKeyParser.NameContext):
        pass

    # Exit a parse tree produced by AriaKeyParser#name.
    def exitName(self, ctx:AriaKeyParser.NameContext):
        pass


    # Enter a parse tree produced by AriaKeyParser#attributes.
    def enterAttributes(self, ctx:AriaKeyParser.AttributesContext):
        pass

    # Exit a parse tree produced by AriaKeyParser#attributes.
    def exitAttributes(self, ctx:AriaKeyParser.AttributesContext):
        pass


    # Enter a parse tree produced by AriaKeyParser#attribute.
    def enterAttribute(self, ctx:AriaKeyParser.AttributeContext):
        pass

    # Exit a parse tree produced by AriaKeyParser#attribute.
    def exitAttribute(self, ctx:AriaKeyParser.AttributeContext):
        pass


    # Enter a parse tree produced by AriaKeyParser#attrName.
    def enterAttrName(self, ctx:AriaKeyParser.AttrNameContext):
        pass

    # Exit a parse tree produced by AriaKeyParser#attrName.
    def exitAttrName(self, ctx:AriaKeyParser.AttrNameContext):
        pass


    # Enter a parse tree produced by AriaKeyParser#attrValue.
    def enterAttrValue(self, ctx:AriaKeyParser.AttrValueContext):
        pass

    # Exit a parse tree produced by AriaKeyParser#attrValue.
    def exitAttrValue(self, ctx:AriaKeyParser.AttrValueContext):
        pass



del AriaKeyParser