# Generated from grammar/AriaKey.g4 by ANTLR 4.13.2
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO

def serializedATN():
    return [
        4,1,9,49,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,6,
        1,0,1,0,3,0,17,8,0,1,0,3,0,20,8,0,1,0,1,0,1,1,1,1,1,2,1,2,1,3,4,
        3,29,8,3,11,3,12,3,30,1,4,1,4,1,4,1,4,1,4,1,4,1,4,1,4,1,4,1,4,3,
        4,43,8,4,1,5,1,5,1,6,1,6,1,6,0,0,7,0,2,4,6,8,10,12,0,2,1,0,5,6,2,
        0,4,5,7,8,45,0,14,1,0,0,0,2,23,1,0,0,0,4,25,1,0,0,0,6,28,1,0,0,0,
        8,42,1,0,0,0,10,44,1,0,0,0,12,46,1,0,0,0,14,16,3,2,1,0,15,17,3,4,
        2,0,16,15,1,0,0,0,16,17,1,0,0,0,17,19,1,0,0,0,18,20,3,6,3,0,19,18,
        1,0,0,0,19,20,1,0,0,0,20,21,1,0,0,0,21,22,5,0,0,1,22,1,1,0,0,0,23,
        24,5,7,0,0,24,3,1,0,0,0,25,26,7,0,0,0,26,5,1,0,0,0,27,29,3,8,4,0,
        28,27,1,0,0,0,29,30,1,0,0,0,30,28,1,0,0,0,30,31,1,0,0,0,31,7,1,0,
        0,0,32,33,5,1,0,0,33,34,3,10,5,0,34,35,5,2,0,0,35,43,1,0,0,0,36,
        37,5,1,0,0,37,38,3,10,5,0,38,39,5,3,0,0,39,40,3,12,6,0,40,41,5,2,
        0,0,41,43,1,0,0,0,42,32,1,0,0,0,42,36,1,0,0,0,43,9,1,0,0,0,44,45,
        5,7,0,0,45,11,1,0,0,0,46,47,7,1,0,0,47,13,1,0,0,0,4,16,19,30,42
    ]

class AriaKeyParser ( Parser ):

    grammarFileName = "AriaKey.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "'['", "']'", "'='", "'mixed'" ]

    symbolicNames = [ "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "STRING", "REGEX", "IDENTIFIER", "NUMBER", 
                      "WS" ]

    RULE_key = 0
    RULE_role = 1
    RULE_name = 2
    RULE_attributes = 3
    RULE_attribute = 4
    RULE_attrName = 5
    RULE_attrValue = 6

    ruleNames =  [ "key", "role", "name", "attributes", "attribute", "attrName", 
                   "attrValue" ]

    EOF = Token.EOF
    T__0=1
    T__1=2
    T__2=3
    T__3=4
    STRING=5
    REGEX=6
    IDENTIFIER=7
    NUMBER=8
    WS=9

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.2")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class KeyContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def role(self):
            return self.getTypedRuleContext(AriaKeyParser.RoleContext,0)


        def EOF(self):
            return self.getToken(AriaKeyParser.EOF, 0)

        def name(self):
            return self.getTypedRuleContext(AriaKeyParser.NameContext,0)


        def attributes(self):
            return self.getTypedRuleContext(AriaKeyParser.AttributesContext,0)


        def getRuleIndex(self):
            return AriaKeyParser.RULE_key

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterKey" ):
                listener.enterKey(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitKey" ):
                listener.exitKey(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitKey" ):
                return visitor.visitKey(self)
            else:
                return visitor.visitChildren(self)




    def key(self):

        localctx = AriaKeyParser.KeyContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_key)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 14
            self.role()
            self.state = 16
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==5 or _la==6:
                self.state = 15
                self.name()


            self.state = 19
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==1:
                self.state = 18
                self.attributes()


            self.state = 21
            self.match(AriaKeyParser.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class RoleContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENTIFIER(self):
            return self.getToken(AriaKeyParser.IDENTIFIER, 0)

        def getRuleIndex(self):
            return AriaKeyParser.RULE_role

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterRole" ):
                listener.enterRole(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitRole" ):
                listener.exitRole(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitRole" ):
                return visitor.visitRole(self)
            else:
                return visitor.visitChildren(self)




    def role(self):

        localctx = AriaKeyParser.RoleContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_role)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 23
            self.match(AriaKeyParser.IDENTIFIER)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class NameContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRING(self):
            return self.getToken(AriaKeyParser.STRING, 0)

        def REGEX(self):
            return self.getToken(AriaKeyParser.REGEX, 0)

        def getRuleIndex(self):
            return AriaKeyParser.RULE_name

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterName" ):
                listener.enterName(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitName" ):
                listener.exitName(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitName" ):
                return visitor.visitName(self)
            else:
                return visitor.visitChildren(self)




    def name(self):

        localctx = AriaKeyParser.NameContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_name)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 25
            _la = self._input.LA(1)
            if not(_la==5 or _la==6):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AttributesContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def attribute(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(AriaKeyParser.AttributeContext)
            else:
                return self.getTypedRuleContext(AriaKeyParser.AttributeContext,i)


        def getRuleIndex(self):
            return AriaKeyParser.RULE_attributes

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterAttributes" ):
                listener.enterAttributes(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitAttributes" ):
                listener.exitAttributes(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAttributes" ):
                return visitor.visitAttributes(self)
            else:
                return visitor.visitChildren(self)




    def attributes(self):

        localctx = AriaKeyParser.AttributesContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_attributes)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 28 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 27
                self.attribute()
                self.state = 30 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==1):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AttributeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def attrName(self):
            return self.getTypedRuleContext(AriaKeyParser.AttrNameContext,0)


        def attrValue(self):
            return self.getTypedRuleContext(AriaKeyParser.AttrValueContext,0)


        def getRuleIndex(self):
            return AriaKeyParser.RULE_attribute

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterAttribute" ):
                listener.enterAttribute(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitAttribute" ):
                listener.exitAttribute(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAttribute" ):
                return visitor.visitAttribute(self)
            else:
                return visitor.visitChildren(self)




    def attribute(self):

        localctx = AriaKeyParser.AttributeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_attribute)
        try:
            self.state = 42
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,3,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 32
                self.match(AriaKeyParser.T__0)
                self.state = 33
                self.attrName()
                self.state = 34
                self.match(AriaKeyParser.T__1)
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 36
                self.match(AriaKeyParser.T__0)
                self.state = 37
                self.attrName()
                self.state = 38
                self.match(AriaKeyParser.T__2)
                self.state = 39
                self.attrValue()
                self.state = 40
                self.match(AriaKeyParser.T__1)
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AttrNameContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENTIFIER(self):
            return self.getToken(AriaKeyParser.IDENTIFIER, 0)

        def getRuleIndex(self):
            return AriaKeyParser.RULE_attrName

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterAttrName" ):
                listener.enterAttrName(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitAttrName" ):
                listener.exitAttrName(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAttrName" ):
                return visitor.visitAttrName(self)
            else:
                return visitor.visitChildren(self)




    def attrName(self):

        localctx = AriaKeyParser.AttrNameContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_attrName)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 44
            self.match(AriaKeyParser.IDENTIFIER)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AttrValueContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENTIFIER(self):
            return self.getToken(AriaKeyParser.IDENTIFIER, 0)

        def STRING(self):
            return self.getToken(AriaKeyParser.STRING, 0)

        def NUMBER(self):
            return self.getToken(AriaKeyParser.NUMBER, 0)

        def getRuleIndex(self):
            return AriaKeyParser.RULE_attrValue

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterAttrValue" ):
                listener.enterAttrValue(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitAttrValue" ):
                listener.exitAttrValue(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAttrValue" ):
                return visitor.visitAttrValue(self)
            else:
                return visitor.visitChildren(self)




    def attrValue(self):

        localctx = AriaKeyParser.AttrValueContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_attrValue)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 46
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 432) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx





