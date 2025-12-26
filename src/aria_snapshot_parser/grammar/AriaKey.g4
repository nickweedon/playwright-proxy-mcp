grammar AriaKey;

// ===== Parser Rules (lowercase) =====

key
    : role name? attributes? EOF
    ;

role
    : IDENTIFIER
    ;

name
    : STRING
    | REGEX
    ;

attributes
    : attribute+
    ;

attribute
    : '[' attrName ']'
    | '[' attrName '=' attrValue ']'
    ;

attrName
    : IDENTIFIER
    ;

attrValue
    : IDENTIFIER
    | STRING
    | NUMBER
    | 'mixed'  // Special value for checked/pressed
    ;

// ===== Lexer Rules (uppercase) =====

// String literals with escape sequences
STRING
    : '"' ( ESC | SAFE_CHAR )* '"'
    ;

fragment ESC
    : '\\' ( ["\\/bfnrt] | 'u' HEX HEX HEX HEX )
    ;

fragment SAFE_CHAR
    : ~["\\\u0000-\u001F]
    ;

fragment HEX
    : [0-9a-fA-F]
    ;

// Regex patterns
REGEX
    : '/' ( '\\' . | ~[/\\\r\n] )+ '/'
    ;

// Identifiers (role names, attribute names)
IDENTIFIER
    : [a-zA-Z_] [a-zA-Z0-9_-]*
    ;

// Numbers (for level attribute)
NUMBER
    : [0-9]+
    ;

// Whitespace (skip)
WS
    : [ \t\r\n]+ -> skip
    ;
