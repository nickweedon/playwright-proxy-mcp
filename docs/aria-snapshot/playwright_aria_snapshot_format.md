# Playwright Accessibility Snapshot Format

## Official Name
**Aria Snapshot** or **Accessibility Tree Snapshot**

## What It Is
A custom YAML-like format created by Microsoft for Playwright that represents the accessibility tree of a web page. It's based on browser accessibility APIs (similar to what screen readers consume) but with a Playwright-specific output format.

## Source Code Location
GitHub: `microsoft/playwright`

**Parser (YAML → AriaNode):**
- `/packages/playwright-core/src/utils/isomorphic/ariaSnapshot.ts`
  - `parseAriaSnapshot()` - Main parser function (line 123)
  - `KeyParser` class - Parses role/name/attributes syntax (line 310)
  - Uses the `yaml` npm package for base YAML parsing
  - Custom parser handles the special syntax: `role "name" [attributes]`

**Generator (DOM → YAML):**
- `/packages/injected/src/ariaSnapshot.ts`
  - `generateAriaTree()` - Generates aria tree from DOM (line 78)
  - `renderAriaTree()` - Converts aria tree to YAML string (line 565)
  - `createKey()` - Formats element keys with role/name/attributes (line 584)

## Data Structure

### TypeScript Types
```typescript
export type AriaNode = AriaProps & {
  role: AriaRole | 'fragment' | 'iframe';
  name: string;
  ref?: string;
  children: (AriaNode | string)[];
  box: AriaBox;
  receivesPointerEvents: boolean;
  props: Record<string, string>;
};

export type AriaProps = {
  checked?: boolean | 'mixed';
  disabled?: boolean;
  expanded?: boolean;
  active?: boolean;
  level?: number;
  pressed?: boolean | 'mixed';
  selected?: boolean;
};

export type AriaBox = {
  visible: boolean;
  inline: boolean;
  cursor?: string;
};
```

### AriaRole Types
Includes 70+ ARIA roles from W3C spec:
- Common: button, link, textbox, checkbox, combobox, etc.
- Container: navigation, main, contentinfo, search, etc.
- Structure: list, listitem, table, row, cell, etc.
- Plus special roles: fragment, iframe, generic

## Format Syntax

### Basic Structure
```yaml
- role "accessible name" [attributes]:
  - child elements or text
```

### Attributes
Enclosed in square brackets:
- `[ref=e4]` - Element reference for interaction
- `[cursor=pointer]` - Has pointer cursor (clickable)
- `[active]` - Currently focused
- `[checked]`, `[checked=mixed]` - Checkbox/radio state
- `[disabled]` - Disabled state
- `[expanded]` - Expanded/collapsed state
- `[level=N]` - Heading level
- `[pressed]`, `[pressed=mixed]` - Toggle button state
- `[selected]` - Selected state

### Properties
Start with `/` for additional metadata:
```yaml
- link "About" [ref=e4]:
  - /url: https://example.com
```

### Text Content
```yaml
- text: "Plain text content"
```

### Example
```yaml
- button "Submit" [ref=e10] [cursor=pointer]
- link "Home" [ref=e5]:
  - /url: https://example.com/
- combobox "Search" [active] [ref=e38]
```

## Parser Implementation

### Key Components

1. **YAML Base Parsing** (uses `yaml` npm package)
   - Parses standard YAML structure
   - Provides position tracking for error messages

2. **KeyParser Class** (custom syntax parser)
   - Parses: `role "name" [attr1] [attr2=value]`
   - Handles:
     - Role identifiers (alphabetic)
     - Quoted strings with escape sequences
     - Regex patterns: `/pattern/`
     - Attributes in brackets

3. **Tree Conversion**
   - Converts YAML sequences to AriaNode children
   - Handles text nodes, role nodes, and properties
   - Validates structure and reports errors

### Parsing Functions

**Main Entry Point:**
```typescript
parseAriaSnapshot(yaml: YamlLibrary, text: string):
  { fragment: AriaTemplateNode, errors: ParsedYamlError[] }
```

**Key Parser:**
```typescript
KeyParser.parse(text: Scalar<string>): AriaTemplateRoleNode | null
```

Internal methods:
- `_readIdentifier()` - Reads role/attribute names
- `_readString()` - Reads quoted strings
- `_readRegex()` - Reads regex patterns `/pattern/`
- `_readAttributes()` - Reads `[attr=value]` blocks
- `_applyAttribute()` - Validates and applies attributes

## Generator Implementation

### Rendering Modes

**AI Mode** (`mode: 'ai'`):
- For AI/LLM consumption
- Includes generic roles
- Shows interactable element refs
- Renders cursor pointers and active states
- Visibility: elements visible to aria OR visually visible

**Expect Mode** (`mode: 'expect'`):
- For test assertions
- Standard aria visibility only
- No refs included

**Codegen Mode** (`mode: 'codegen'`):
- Generates test templates with regex
- Converts dynamic content (numbers, sizes) to regex patterns

**Autoexpect Mode** (`mode: 'autoexpect'`):
- Auto-generate assertions on visible elements
- Requires both aria and visual visibility

### Generation Process

1. **DOM Traversal** (`generateAriaTree()`)
   - Walks DOM tree starting from root element
   - Extracts ARIA roles, names, and properties
   - Computes visibility and interactability
   - Assigns refs to interactable elements
   - Builds AriaNode tree structure

2. **Tree Rendering** (`renderAriaTree()`)
   - Converts AriaNode tree to YAML string
   - Formats keys: `role "name" [attributes]`
   - Handles text escaping with `yamlEscapeKeyIfNeeded()`
   - Inlines single text children
   - Outputs properties with `/` prefix

3. **Key Formatting** (`createKey()`)
   - Combines role + name + attributes
   - Limits name to 900 chars (YAML key limit is 1024)
   - Adds attribute markers in order
   - Returns formatted key string

### Special Features

**Regex Generation:**
- Converts dynamic content to regex patterns
- Patterns for: file sizes (2mb), times (2ms), numbers (22, 2.33)
- Used in codegen mode for robust test assertions

**Diff Support:**
- Can compare snapshots
- Marks changed elements with `<changed>`
- Shows unchanged refs: `ref=e4 [unchanged]`

## No Standard Grammar File

There is **no published ANTLR or formal grammar specification**. The format is defined entirely by:
1. The TypeScript implementation in Playwright source code
2. The parser/generator code shown above

## Querying This Format

### Not Queryable With:
- **JMESPath** - Requires JSON, this is YAML-like text
- **Standard YAML libraries** - Custom syntax not standard YAML
- **XPath** - Requires XML/DOM structure
- **CSS Selectors** - Not applicable to this format

### How to Work With It:

1. **Use Element References**
   - The `ref` values (e.g., `ref=e4`) are designed for interaction
   - Pass refs to Playwright MCP tools: `browser_click`, `browser_type`, etc.

2. **Parse with Playwright's Own Code**
   - Use `parseAriaSnapshot()` from Playwright source
   - Returns structured `AriaNode` tree you can traverse in JavaScript/TypeScript

3. **Text Processing**
   - Regex matching on the text output
   - String search for specific roles/names
   - Line-by-line parsing

4. **Use Playwright API Directly**
   - `page.locator()` with role/name selectors
   - `page.getByRole('button', { name: 'Submit' })`
   - Better than parsing the snapshot

## Design Philosophy

The format is designed for:
- **Human readability** - Easy to understand in test outputs and diffs
- **Accessibility testing** - Shows what screen readers would see
- **Browser automation** - Refs enable element interaction
- **Token efficiency** - More compact than HTML/DOM for AI/LLM use

It is **NOT** designed for:
- Programmatic querying
- Data extraction
- Automated filtering
- Schema validation

The lack of a query interface is intentional - use Playwright's locator API instead.
