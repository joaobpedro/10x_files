# NOTE: this is an entrance for the things I need to implement
#
#------------------------------------------------------------------------
# List of things that I want on my editor:
#   X gather all TODOS and NOTES from a project and pipe it to the build output
#   X this is working grest now :)
#   X delete current work
#   - make an increment list items like the Vim thing
#------------------------------------------------------------------------

import N10X
import re ## regular expressions, super handy for things with text
import os

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
    if not N10X.Editor.TextEditorHasFocus():
        return

    _, current_y = N10X.Editor.GetCursorPos()
    line_count = N10X.Editor.GetLineCount()

    # --- Phase 1: Find Table Boundaries ---
    start_y = current_y
    while start_y > 0:
        prev_line = N10X.Editor.GetLine(start_y - 1).strip()
        if not prev_line.startswith('|') or not prev_line.endswith('|'):
            break
        start_y -= 1

    end_y = current_y
    while end_y < line_count - 1:
        next_line = N10X.Editor.GetLine(end_y + 1).strip()
        if not next_line.startswith('|') or not next_line.endswith('|'):
            break
        end_y += 1

    current_line_text = N10X.Editor.GetLine(current_y).strip()
    if not current_line_text.startswith('|') or not current_line_text.endswith('|'):
        N10X.Editor.SetStatusBarText("Not inside a Markdown table block.")
        return

    # --- Phase 2: Parse Rows Safely ---
    raw_rows = []
    is_separator_row = {}
    max_num_columns = 0

    for idx, y in enumerate(range(start_y, end_y + 1)):
        line_text = N10X.Editor.GetLine(y).strip()
        
        # BUG FIX HERE: 
        # Instead of a simple split that gets tripped up by trailing pipes,
        # strip exactly ONE leading and ONE trailing pipe, then split.
        if line_text.startswith('|'): line_text = line_text[1:]
        if line_text.endswith('|'): line_text = line_text[:-1]
        
        cells = [cell.strip() for cell in line_text.split('|')]
        
        # Check if it's a separator row (e.g., |---|---|)
        is_sep = all(all(c in '-: ' for c in cell) for cell in cells) if cells else False
        is_separator_row[idx] = is_sep
        
        raw_rows.append(cells)
        if len(cells) > max_num_columns:
            max_num_columns = len(cells)

    # Balance rows and compute maximum column widths
    max_col_widths = {}
    for idx, cells in enumerate(raw_rows):
        # Pad shorter rows up to match the maximum column count
        while len(cells) < max_num_columns:
            cells.append("")
            
        raw_rows[idx] = cells

        # Only measure text width on data rows
        if not is_separator_row[idx]:
            for col_idx, cell in enumerate(cells):
                cell_len = len(cell)
                if col_idx not in max_col_widths or cell_len > max_col_widths[col_idx]:
                    max_col_widths[col_idx] = cell_len

    # Default fallback for empty columns
    for col_idx in range(max_num_columns):
        if col_idx not in max_col_widths or max_col_widths[col_idx] < 3:
            max_col_widths[col_idx] = 3

    # --- Phase 3: Format and Rewrite Lines ---
    N10X.Editor.PushUndoGroup()
    N10X.Editor.BeginTextUpdate()

    for idx, y in enumerate(range(start_y, end_y + 1)):
        cells = raw_rows[idx]
        formatted_cells = []
        
        if is_separator_row[idx]:
            for col_idx in range(max_num_columns):
                width = max_col_widths.get(col_idx, 3)
                formatted_cells.append("-" * (width + 2))
        else:
            for col_idx in range(max_num_columns):
                width = max_col_widths.get(col_idx, 3)
                cell_text = cells[col_idx]
                padded_text = cell_text.ljust(width)
                formatted_cells.append(f" {padded_text} ")

        new_row_text = "|" + "|".join(formatted_cells) + "|"
        N10X.Editor.SetLine(y, new_row_text)

    N10X.Editor.EndTextUpdate()
    N10X.Editor.PopUndoGroup()
    N10X.Editor.SetStatusBarText("Table auto-completed and formatted!")

# To make it run automatically on save, use AddPreFileSaveFunction
def OnPreSave(filename):
    FormatMarkdownTables()

# Register the callback
# N10X.AddPreFileSaveFunction(OnPreSave)
N10X.Editor.AddPreFileSaveFunction(OnPreSave)

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
def HighlightCurrentLine():
    # 1. Get the current line index
    _, line_index = N10X.Editor.GetCursorPos()
    
    # 2. Get the text of the line to find its length (to highlight to the very end)
    line_text = N10X.Editor.GetLine(line_index)
    line_length = len(line_text.rstrip()) if line_text else 0
    
    # 3. Set the selection range: (start_col, start_line) to (end_col, end_line)
    # This automatically applies the editor's "selection highlight"
    N10X.Editor.SetSelection((0, line_index), (line_length, line_index))


#------------------------------------------------------------------------
def MoveCursorParagraphUp():
    if not N10X.Editor.TextEditorHasFocus():
        return

    cx, current_y = N10X.Editor.GetCursorPos()
    
    # If already at the first line, do nothing
    if current_y <= 0:
        return

    target_y = 0
    inside_current_block = True
    line_count = N10X.Editor.GetLineCount()

    # Scan upward starting from the line above the cursor
    for y in range(current_y - 1, -1, -1):
        line_text = N10X.Editor.GetLine(y).strip()
        if inside_current_block:
            # If we were in text and hit an empty line, we've exited the current paragraph
            if not line_text:
                inside_current_block = False
        else:
            # Stop at the first non-empty line we encounter moving upward
            if line_text:
                target_y = y
                break

    # Set the cursor to column 0 of the target line
    N10X.Editor.SetCursorPos((0, target_y))
    N10X.Editor.ScrollCursorIntoView()

def MoveCursorParagraphDown():
    if not N10X.Editor.TextEditorHasFocus():
        return

    cx, current_y = N10X.Editor.GetCursorPos()
    line_count = N10X.Editor.GetLineCount()
        
    # If already at the last line, do nothing
    if current_y >= line_count - 1:
        return

    target_y = line_count - 1
    inside_current_block = True

    # Scan downward starting from the line below the cursor
    for y in range(current_y + 1, line_count):
        line_text = N10X.Editor.GetLine(y).strip()
        
        if inside_current_block:
            # If we were in text and hit an empty line, that's the boundary
            if not line_text:
                inside_current_block = False
        else:
            # Once we are past the empty space, stop at the first line of the next paragraph
            if line_text:
                target_y = y
                break

    # If we hit the end of the file without finding a new paragraph, 
    # default to the last line.
    N10X.Editor.SetCursorPos((0, target_y))
    N10X.Editor.ScrollCursorIntoView()


#------------------------------------------------------------------------
# select paragraph
#------------------------------------------------------------------------
# SetSelection((start_x, start_y), (end_x, end_y), cursor_index=0)
# 1. get the get the cursor position
# 2. Navigate up and down the lines until empty line
# 3. Get coordinates of those lines
# 4. Set selection command for the coordinates
#------------------------------------------------------------------------
def SelectParagraph():
    if not N10X.Editor.TextEditorHasFocus():
        return;
    
    # x is the column and y is the line
    cx, cy = N10X.Editor.GetCursorPos();
    line_count = N10X.Editor.GetLineCount()

    target_down_y = 0;
    target_up_y = 0;
    inside_paragraph = True;

    for y in range(cy + 1, line_count):
        line_text = N10X.Editor.GetLine(y).strip();

        if inside_paragraph:
            if not line_text:
                inside_paragraph = False;
                target_down_y = y-1;
                break;
  
    inside_paragraph = True;
    for y in range(cy - 1, -1, -1):
        line_text = N10X.Editor.GetLine(y).strip();

        if inside_paragraph:
            if not line_text:
                inside_paragraph = False;
                target_up_y = y+1;
                break;
   
    #set the selection
    #get last line length
    last_line_length = len(N10X.Editor.GetLine(target_down_y).rstrip());
    N10X.Editor.SetSelection((0, target_up_y), (last_line_length, target_down_y), cursor_index=0)

    return
#------------------------------------------------------------------------
# need to get all the todos
# 1. use the 10X workspace search
# 2. go through the files and filter out the ones that are not in the
#    worksapce root
# 3. send each remaining file to the build panel
#------------------------------------------------------------------------
def OnTodoSearchFinished(results, truncated):
    """Callback fired by 10x when the native workspace search completes."""
    # 1. Prepare the Build Panel
    N10X.Editor.ClearBuildOutput()
    N10X.Editor.ShowBuildOutput()

    if not results:
        N10X.Editor.LogToBuildOutput("=== No TODOs found in the workspace ===\n")
        N10X.Editor.SetStatusBarText("TODO Search: 0 matches found.")
        return

    N10X.Editor.LogToBuildOutput(f"=== Workspace TODOs ({len(results)} found) ===\n")
    

    #get the root folder
    workspace_path = N10X.Editor.GetWorkspaceFilename()
    if not workspace_path:
        N10X.Editor.LogTo10XOutput("Error: No workspace currently open.")
        return
    root_folder = os.path.normpath(os.path.dirname(workspace_path))

    root_results = []
    if results:
        for item in results:
            filename = item[0] # item[0] is the absolute file path
            file_dir = os.path.normpath(os.path.dirname(filename))

            print("File dir = ", file_dir)
            print("Root dir  = ", root_folder)
            
            # If the file's directory exactly matches the root directory, keep it!
            if file_dir == root_folder:
                root_results.append(item)

    # 2. Format the results as compiler information lines
    for filename, char_index, line_index, line_text in root_results:
        clean_text = line_text.strip()
        # The formatting "file(line): info: text" makes it clickable in the build panel
        formatted_line = f"{filename}({line_index + 1}): info: {clean_text}\n"
        N10X.Editor.LogToBuildOutput(formatted_line)

    if truncated:
        N10X.Editor.LogToBuildOutput("\n... [Warning: Results truncated by search limit] ...\n")
        
    N10X.Editor.LogToBuildOutput("=== Scan Completed ===")
    
    # 3. Tell 10x to parse the text so the links become active
    N10X.Editor.ParseBuildOutput()
    N10X.Editor.SetStatusBarText(f"TODO Search complete. Found {len(results)} items.")



def ListTodos():
    """Main function to bind to your keyboard."""
    N10X.Editor.SetStatusBarText("Searching workspace for TODOs...")
    
    # Fire the asynchronous native search for "TODO" (case-insensitive)
    N10X.Editor.FindTextInFiles(
        "TODO:", 
        OnTodoSearchFinished, 
        True,     # Catches TODO, todo, ToDo
        False, 
        False
    )

#------------------------------------------------------------------------
def DeleteWord():
    if not N10X.Editor.TextEditorHasFocus():
        return
    N10X.Editor.PushUndoGroup()
    N10X.Editor.ExecuteCommand("SelectCurrentWord")
    N10X.Editor.ExecuteCommand("Delete")
    N10X.Editor.PopUndoGroup()