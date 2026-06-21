import N10X
import re

#------------------------------------------------------------------------
def ToggleCheckbox():
    """
    Adds [ ] if none exists.
    Changes [ ] to [x] if complete.
    Changes [x] to [ ] if imcomplete.
    """
    line_index = N10X.Editor.GetCursorPos()[1]
    line_text = N10X.Editor.GetLine(line_index)
    
    # Patterns
    is_empty_check = re.match(r"^(\s*)-\s\[\s\]\s(.*)", line_text)
    is_full_check = re.match(r"^(\s*)-\s\[x\]\s(.*)", line_text)
    is_bullet = re.match(r"^(\s*)-\s(.*)", line_text)

    if is_empty_check:
        # Mark Complete
        new_line = line_text.replace("[ ]", "[x]", 1)
    elif is_full_check:
        # Mark Incomplete
        new_line = line_text.replace("[x]", "[ ]", 1)
    elif is_bullet:
        # Convert bullet to checkbox
        new_line = line_text.replace("- ", "- [ ] ", 1)
    else:
        # Add checkbox to plain text
        # Finding leading whitespace to preserve indentation
        whitespace = re.match(r"^\s*", line_text).group(0)
        content = line_text.lstrip()
        new_line = f"{whitespace}- [ ] {content}"

    N10X.Editor.SetLine(line_index, new_line)

#------------------------------------------------------------------------
def RemoveCheckbox():
    """
    Removes any markdown checkbox or bullet from the start of the line.
    """
    line_index = N10X.Editor.GetCursorPos()[1]
    line_text = N10X.Editor.GetLine(line_index)
    
    # Regex to strip '- [ ] ', '- [x] ', or just '- ' while keeping indentation
    new_line = re.sub(r"^(\s*)-\s(\[[\sx]\]\s)?", r"\1", line_text)
    
    N10X.Editor.SetLine(line_index, new_line)

#------------------------------------------------------------------------
def FormatMarkdownTables():
    # Get the current filename to check extension
    filename = N10X.Editor.GetCurrentFilename()
    if not filename or not filename.lower().endswith((".md", ".markdown")):
        return

    # Use GetFileText/SetFileText as per 10x Documentation
    text = N10X.Editor.GetFileText()
    if not text:
        return

    lines = text.splitlines()
    formatted_lines = []
    i = 0

    while i < len(lines):
        line_strip = lines[i].strip()
        # Basic check for a markdown table line
        if line_strip.startswith('|') and line_strip.endswith('|') and len(line_strip) > 1 :
            table_rows = []
            # Gather all consecutive table lines
            while i < len(lines) and lines[i].strip().startswith('|'):
                raw_cells = lines[i].split('|')
                # 10x split will have empty strings at index 0 and -1 due to leading/trailing pipes
                cells = [c.strip() for c in raw_cells[1:-1]]
                table_rows.append(cells)
                i += 1
            
            if not table_rows:
                continue

            # Calculate column widths
            num_cols = max(len(row) for row in table_rows)
            widths = [0] * num_cols
            for row in table_rows:
                for idx, cell in enumerate(row):
                    if idx < num_cols:
                        widths[idx] = max(widths[idx], len(cell))

            # Build the aligned table
            for row in table_rows:
                # Detect if it's a separator line (contains only -, :, and space)
                is_sep = all(all(c in '-: ' for c in cell) for cell in row)
                
                formatted_row = "|"
                for idx in range(num_cols):
                    val = row[idx] if idx < len(row) else ""
                    if is_sep:
                        # Standardize separator to match width
                        formatted_row += "-" * (widths[idx] + 2) + "|"
                    else:
                        formatted_row += f" {val.ljust(widths[idx])} |"
                formatted_lines.append(formatted_row)
        else:
            formatted_lines.append(lines[i])
            i += 1

    new_text = "\n".join(formatted_lines)

    if new_text != text:
        # 10x API uses BeginTextUpdate/EndTextUpdate for performance
        N10X.Editor.BeginTextUpdate()
        N10X.Editor.SetFileText(new_text)
        N10X.Editor.EndTextUpdate()
        N10X.Editor.LogTo10XOutput("Markdown tables formatted.")

# To make it run automatically on save, use AddPreFileSaveFunction
def OnPreSave(filename):
    FormatMarkdownTables()

# Register the callback
# N10X.AddPreFileSaveFunction(OnPreSave)
N10X.Editor.AddPreFileSaveFunction(OnPreSave)
# Also expose it as a command you can run via Ctrl+Shift+X
# Just defining the function at top level makes it a command in 10x




#------------------------------------------------------------------------

SCROLL_MARGIN = 10

def force_margins():
    # Set the desired  padding margin (number of lines from top/bottom)

    # Only run if a text editor window actually has focus
    if not N10X.Editor.TextEditorHasFocus():
        return

    # Get the line index where the cursor currently resides
    _, cursor_y = N10X.Editor.GetCursorPos()
    
    # Get the line index currently at the very top of the visible screen
    scroll_top_y = N10X.Editor.GetScrollLine()
    
    # Get the total number of lines currently visible in the view window
    visible_lines = N10X.Editor.GetVisibleLineCount()
    scroll_bottom_y = scroll_top_y + visible_lines

    # --- Case 1: Cursor is moving near the TOP boundary ---
    if cursor_y < (scroll_top_y + SCROLL_MARGIN):
        # Calculate the new top scroll line to maintain the margin
        new_scroll_top = cursor_y - SCROLL_MARGIN
        # Don't scroll past the top of the document (line 0)
        if new_scroll_top < 0:
            new_scroll_top = 0
            
        if new_scroll_top != scroll_top_y:
            N10X.Editor.SetScrollLine(new_scroll_top)

    # --- Case 2: Cursor is moving near the BOTTOM boundary ---
    elif cursor_y > (scroll_bottom_y - SCROLL_MARGIN - 1):
        # Calculate the new top scroll position required to push the view down
        new_scroll_top = cursor_y - visible_lines + SCROLL_MARGIN + 1
        max_scroll = N10X.Editor.GetLineCount() - visible_lines
        
        if new_scroll_top > max_scroll:
            new_scroll_top = max_scroll
            
        if new_scroll_top > scroll_top_y and new_scroll_top >= 0:
            N10X.Editor.SetScrollLine(new_scroll_top)


N10X.Editor.AddCursorMovedFunction(force_margins)

#------------------------------------------------------------------------
BRACE_MAP = {
    '{': '}',
}

def FindEnclosingBrace(start_x, start_y):
    """
    Scans backward to find if the cursor is currently inside a bracket pair.
    Returns (open_pos, close_pos, open_char, close_char) if found, else None.
    """
    line_count = N10X.Editor.GetLineCount()
    
    # Track nesting when scanning backward
    # Key: closing character, Value: count of unmatched closing characters seen
    reverse_nest = { '}': 0}

    # Step 1: Scan backward from current position for an unmatched opening bracket
    for y in range(start_y, -1, -1):
        line_text = N10X.Editor.GetLine(y)
        x_start = (start_x - 1) if y == start_y else (len(line_text) - 1)
        
        for x in range(x_start, -1, -1):
            char = line_text[x]
            
            if char in reverse_nest:
                reverse_nest[char] += 1
            elif char in BRACE_MAP:
                close_char = BRACE_MAP[char]
                if reverse_nest[close_char] > 0:
                    reverse_nest[close_char] -= 1
                else:
                    # Found the active opening bracket!
                    open_pos = (x + 1, y)
                    
                    # Step 2: Now verify the matching closing bracket is AFTER our original cursor
                    match_pos = FindMatchingClose(x + 1, y, char, close_char, line_count)
                    if match_pos and IsPosAfter(match_pos, (start_x, start_y)):
                        return open_pos, match_pos, char, close_char
    return None

def FindMatchingClose(start_x, start_y, open_char, close_char, line_count):
    """Scans forward to find the matching close character."""
    nest_level = 1
    for y in range(start_y, line_count):
        line_text = N10X.Editor.GetLine(y)
        x_start = start_x if y == start_y else 0
        
        for x in range(x_start, len(line_text)):
            char = line_text[x]
            if char == open_char:
                nest_level += 1
            elif char == close_char:
                nest_level -= 1
                if nest_level == 0:
                    return (x, y)
    return None

def IsPosAfter(pos1, pos2):
    """Returns True if pos1 is after pos2 in the document."""
    x1, y1 = pos1
    x2, y2 = pos2
    if y1 > y2: return True
    if y1 == y2 and x1 > x2: return True
    return False

def SelectInsideNextBraces():
    current_file = N10X.Editor.GetCurrentFilename()
    if not current_file:
        return

    start_x, start_y = N10X.Editor.GetCursorPos()
    line_count = N10X.Editor.GetLineCount()

    # --- PRIORITY 1: Check if we are ALREADY inside a pair ---
    enclosing = FindEnclosingBrackets(start_x, start_y)
    if enclosing:
        open_pos, close_pos, open_char, close_char = enclosing
        N10X.Editor.SetSelection(open_pos, close_pos, 0)
        N10X.Editor.CenterViewAtLinePos(close_pos[1])
        N10X.Editor.SetStatusBarText(f"Selected inside current {open_char}{close_char}")
        return

    # --- PRIORITY 2: Fallback to looking ahead ---
    found_open = False
    open_char = ''
    close_char = ''
    open_pos = (0, 0)

    for y in range(start_y, line_count):
        line_text = N10X.Editor.GetLine(y)
        x_start = start_x if y == start_y else 0
        
        for x in range(x_start, len(line_text)):
            char = line_text[x]
            if char in BRACE_MAP:
                open_char = char
                close_char = BRACE_MAP[char]
                open_pos = (x + 1, y)
                found_open = True
                break
        if found_open:
            break

    if not found_open:
        N10X.Editor.SetStatusBarText("No brackets found inside or ahead.")
        return

    close_pos = FindMatchingClose(open_pos[0], open_pos[1], open_char, close_char, line_count)

    if close_pos:
        N10X.Editor.SetSelection(open_pos, close_pos, 0)
        N10X.Editor.CenterViewAtLinePos(close_pos[1])
        N10X.Editor.SetStatusBarText(f"Selected next upcoming {open_char}{close_char}")
    else:
        N10X.Editor.SetStatusBarText("Mismatched brackets ahead.")

#------------------------------------------------------------------------
BRACKET_MAP = {
    '[': ']',
    '(': ')'
}

def FindEnclosingBrackets(start_x, start_y):
    """
    Scans backward to find if the cursor is currently inside a bracket pair.
    Returns (open_pos, close_pos, open_char, close_char) if found, else None.
    """
    line_count = N10X.Editor.GetLineCount()
    
    # Track nesting when scanning backward
    # Key: closing character, Value: count of unmatched closing characters seen
    reverse_nest = { ']': 0, ')': 0 }

    # Step 1: Scan backward from current position for an unmatched opening bracket
    for y in range(start_y, -1, -1):
        line_text = N10X.Editor.GetLine(y)
        x_start = (start_x - 1) if y == start_y else (len(line_text) - 1)
        
        for x in range(x_start, -1, -1):
            char = line_text[x]
            
            if char in reverse_nest:
                reverse_nest[char] += 1
            elif char in BRACKET_MAP:
                close_char = BRACKET_MAP[char]
                if reverse_nest[close_char] > 0:
                    reverse_nest[close_char] -= 1
                else:
                    # Found the active opening bracket!
                    open_pos = (x + 1, y)
                    
                    # Step 2: Now verify the matching closing bracket is AFTER our original cursor
                    match_pos = FindMatchingClose(x + 1, y, char, close_char, line_count)
                    if match_pos and IsPosAfter(match_pos, (start_x, start_y)):
                        return open_pos, match_pos, char, close_char
    return None

def FindMatchingClose(start_x, start_y, open_char, close_char, line_count):
    """Scans forward to find the matching close character."""
    nest_level = 1
    for y in range(start_y, line_count):
        line_text = N10X.Editor.GetLine(y)
        x_start = start_x if y == start_y else 0
        
        for x in range(x_start, len(line_text)):
            char = line_text[x]
            if char == open_char:
                nest_level += 1
            elif char == close_char:
                nest_level -= 1
                if nest_level == 0:
                    return (x, y)
    return None

def IsPosAfter(pos1, pos2):
    """Returns True if pos1 is after pos2 in the document."""
    x1, y1 = pos1
    x2, y2 = pos2
    if y1 > y2: return True
    if y1 == y2 and x1 > x2: return True
    return False

def SelectInsideNextBrackets():
    current_file = N10X.Editor.GetCurrentFilename()
    if not current_file:
        return

    start_x, start_y = N10X.Editor.GetCursorPos()
    line_count = N10X.Editor.GetLineCount()

    # --- PRIORITY 1: Check if we are ALREADY inside a pair ---
    enclosing = FindEnclosingBrackets(start_x, start_y)
    if enclosing:
        open_pos, close_pos, open_char, close_char = enclosing
        N10X.Editor.SetSelection(open_pos, close_pos, 0)
        N10X.Editor.CenterViewAtLinePos(close_pos[1])
        N10X.Editor.SetStatusBarText(f"Selected inside current {open_char}{close_char}")
        return

    # --- PRIORITY 2: Fallback to looking ahead ---
    found_open = False
    open_char = ''
    close_char = ''
    open_pos = (0, 0)

    for y in range(start_y, line_count):
        line_text = N10X.Editor.GetLine(y)
        x_start = start_x if y == start_y else 0
        
        for x in range(x_start, len(line_text)):
            char = line_text[x]
            if char in BRACKET_MAP:
                open_char = char
                close_char = BRACKET_MAP[char]
                open_pos = (x + 1, y)
                found_open = True
                break
        if found_open:
            break

    if not found_open:
        N10X.Editor.SetStatusBarText("No brackets found inside or ahead.")
        return

    close_pos = FindMatchingClose(open_pos[0], open_pos[1], open_char, close_char, line_count)

    if close_pos:
        N10X.Editor.SetSelection(open_pos, close_pos, 0)
        N10X.Editor.CenterViewAtLinePos(close_pos[1])
        N10X.Editor.SetStatusBarText(f"Selected next upcoming {open_char}{close_char}")
    else:
        N10X.Editor.SetStatusBarText("Mismatched brackets ahead.")



#------------------------------------------------------------------------
def CopyEntireSelectedLines():
    # Get the precise coordinates of the active selection highlight
    start_pos = N10X.Editor.GetSelectionStart()
    end_pos = N10X.Editor.GetSelectionEnd()

    # If there's no active selection, fallback to copying just the current single line
    if start_pos == end_pos:
        _, current_y = N10X.Editor.GetCursorPos()
        line_text = N10X.Editor.GetLine(current_y)
        # Use 10x's InsertText trick or standard system commands to pipe to clipboard.
        # However, 10x has an internal action for this, or we can use standard commands:
        N10X.Editor.ExecuteCommand("Copy")
        N10X.Editor.SetStatusBarText("Copied current line.")
        return

    # Determine top and bottom rows regardless of selection drag direction
    start_y = min(start_pos[1], end_pos[1])
    end_y = max(start_pos[1], end_pos[1])

    copied_lines = []

    # Loop through each line in the row range and harvest the full text
    for y in range(start_y, end_y + 1):
        line_text = N10X.Editor.GetLine(y)
        # Preserve line breaks accurately
        copied_lines.append(line_text.rstrip('\r\n'))

    # Join lines back together with proper newline breaks
    full_text_block = "\n".join(copied_lines) + "\n"

    # --- Transfer to Clipboard ---
    # We leverage 10x's temporary selection state strategy to populate the OS clipboard natively
    original_selection = (start_pos, end_pos, N10X.Editor.GetCursorPos())
    
    # 1. Expand selection visually to full width across all involved rows
    last_line_len = len(N10X.Editor.GetLine(end_y))
    N10X.Editor.SetSelection((0, start_y), (last_line_len, end_y), 0)
    
    # 2. Fire native Copy command
    N10X.Editor.ExecuteCommand("Copy")
    
    # 3. Restore user's original partial selection so their cursor doesn't jump
    N10X.Editor.SetSelection(original_selection[0], original_selection[1], 0)
    N10X.Editor.SetCursorPos(original_selection[2])

    # Provide UI feedback
    total_lines = (end_y - start_y) + 1
    N10X.Editor.SetStatusBarText(f"Copied {total_lines} full lines to clipboard.")


#------------------------------------------------------------------------


def SelectCurrentLine():
    # Get current cursor position (column, line)
    pos = N10X.Editor.GetCursorPos()
    line_index = pos[1]
    
    # Set the cursor to the start of the line (column 0)
    N10X.Editor.SetCursorPos((0, line_index))
    
    # Start the selection
    N10X.Editor.ExecuteCommand("StartSelecting")
    
    # Move the cursor to the end of the line
    # Note: Using a large column number or the MoveLineEnd command
    N10X.Editor.ExecuteCommand("MoveLineEnd")


def HighlightCurrentLine():
    # 1. Get the current line index
    _, line_index = N10X.Editor.GetCursorPos()
    
    # 2. Get the text of the line to find its length (to highlight to the very end)
    line_text = N10X.Editor.GetLine(line_index)
    line_length = len(line_text) if line_text else 0
    
    # 3. Set the selection range: (start_col, start_line) to (end_col, end_line)
    # This automatically applies the editor's "selection highlight"
    N10X.Editor.SetSelection((0, line_index), (line_length, line_index))

