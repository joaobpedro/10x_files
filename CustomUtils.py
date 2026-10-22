import N10X
import re
import os

# ========================================================================
# PRE-COMPILED REGULAR EXPRESSIONS (Optimized for Speed)
# ========================================================================
RE_EMPTY_CHECK = re.compile(r"^(\s*)-\s\[\s\]\s(.*)")
RE_FULL_CHECK  = re.compile(r"^(\s*)-\s\[x\]\s(.*)", re.IGNORECASE)
RE_BULLET      = re.compile(r"^(\s*)-\s(.*)")
RE_LEADING_WS  = re.compile(r"^(\s*)(.*)")
RE_REMOVE_CB   = re.compile(r"^(\s*)-\s(?:\[[\sxX]\]\s)?")
RE_WORDS       = re.compile(r"\w+")
RE_MULTI_SPACE = re.compile(r"[ \t]+")
RE_NUMBER      = re.compile(r"\d+")

# ========================================================================
# WHITESPACE NORMALIZATION
# ========================================================================
def NormalizeWhitespace():
    """
    Collapses multiple horizontal spaces/tabs into a single space.
    Strictly preserves leading whitespace before the selection (and leading 
    indentation on the line if the selection starts at column 0).
    """
    if not N10X.Editor.TextEditorHasFocus():
        return

    start_pos = N10X.Editor.GetSelectionStart()
    end_pos = N10X.Editor.GetSelectionEnd()

    N10X.Editor.PushUndoGroup()
    N10X.Editor.BeginTextUpdate()

    # Case 1: No active selection -> Normalize current line(s) after indentation
    if start_pos == end_pos:
        lines = {N10X.Editor.GetCursorPos(i)[1] for i in range(N10X.Editor.GetCursorCount())}
        for y in sorted(lines):
            line = N10X.Editor.GetLine(y)
            if not line:
                continue
            line_clean = line.rstrip('\r\n')
            eol = line[len(line_clean):]
            
            match = RE_LEADING_WS.match(line_clean)
            if match:
                leading_ws, content = match.groups()
                new_content = RE_MULTI_SPACE.sub(" ", content)
                N10X.Editor.SetLine(y, leading_ws + new_content + eol)

    # Case 2: Active selection
    else:
        if (start_pos[1], start_pos[0]) > (end_pos[1], end_pos[0]):
            start_pos, end_pos = end_pos, start_pos

        start_x, start_y = start_pos
        end_x, end_y = end_pos

        # Single-line selection
        if start_y == end_y:
            line = N10X.Editor.GetLine(start_y)
            if line:
                line_clean = line.rstrip('\r\n')
                eol = line[len(line_clean):]

                prefix = line_clean[:start_x]
                selected = line_clean[start_x:end_x]
                suffix = line_clean[end_x:]

                # If selection includes the start of the line, protect line indentation
                if prefix == "" or prefix.isspace():
                    m = RE_LEADING_WS.match(selected)
                    lead_in_sel, rest_sel = m.groups()
                    norm_sel = lead_in_sel + RE_MULTI_SPACE.sub(" ", rest_sel)
                else:
                    norm_sel = RE_MULTI_SPACE.sub(" ", selected)

                N10X.Editor.SetLine(start_y, prefix + norm_sel + suffix + eol)
                N10X.Editor.SetSelection((start_x, start_y), (start_x + len(norm_sel), end_y))

        # Multi-line selection
        else:
            for y in range(start_y, end_y + 1):
                line = N10X.Editor.GetLine(y)
                if not line:
                    continue
                line_clean = line.rstrip('\r\n')
                eol = line[len(line_clean):]

                if y == start_y:
                    prefix = line_clean[:start_x]
                    selected = line_clean[start_x:]
                    if prefix == "" or prefix.isspace():
                        m = RE_LEADING_WS.match(selected)
                        norm_sel = m.group(1) + RE_MULTI_SPACE.sub(" ", m.group(2))
                    else:
                        norm_sel = RE_MULTI_SPACE.sub(" ", selected)
                    N10X.Editor.SetLine(y, prefix + norm_sel + eol)

                elif y == end_y:
                    selected = line_clean[:end_x]
                    suffix = line_clean[end_x:]
                    m = RE_LEADING_WS.match(selected)
                    norm_sel = m.group(1) + RE_MULTI_SPACE.sub(" ", m.group(2))
                    N10X.Editor.SetLine(y, norm_sel + suffix + eol)

                else:
                    m = RE_LEADING_WS.match(line_clean)
                    norm_line = m.group(1) + RE_MULTI_SPACE.sub(" ", m.group(2))
                    N10X.Editor.SetLine(y, norm_line + eol)

    N10X.Editor.EndTextUpdate()
    N10X.Editor.PopUndoGroup()


# ========================================================================
# CHECKBOX UTILITIES (Multi-Cursor Friendly)
# ========================================================================
def _get_unique_cursor_lines():
    return sorted({N10X.Editor.GetCursorPos(i)[1] for i in range(N10X.Editor.GetCursorCount())})

def ToggleCheckbox():
    if not N10X.Editor.TextEditorHasFocus():
        return

    N10X.Editor.PushUndoGroup()
    N10X.Editor.BeginTextUpdate()

    for line_index in _get_unique_cursor_lines():
        line_text = N10X.Editor.GetLine(line_index)
        if line_text is None:
            continue

        line_clean = line_text.rstrip('\r\n')
        eol = line_text[len(line_clean):]

        if RE_EMPTY_CHECK.match(line_clean):
            new_line = line_clean.replace("[ ]", "[x]", 1)
        elif RE_FULL_CHECK.match(line_clean):
            new_line = RE_FULL_CHECK.sub(r"\1- [ ] \2", line_clean)
        elif RE_BULLET.match(line_clean):
            new_line = line_clean.replace("- ", "- [ ] ", 1)
        else:
            whitespace, content = RE_LEADING_WS.match(line_clean).groups()
            new_line = f"{whitespace}- [ ] {content}"

        N10X.Editor.SetLine(line_index, new_line + eol)

    N10X.Editor.EndTextUpdate()
    N10X.Editor.PopUndoGroup()

def RemoveCheckbox():
    if not N10X.Editor.TextEditorHasFocus():
        return

    N10X.Editor.PushUndoGroup()
    N10X.Editor.BeginTextUpdate()

    for line_index in _get_unique_cursor_lines():
        line_text = N10X.Editor.GetLine(line_index)
        if line_text is not None:
            new_line = RE_REMOVE_CB.sub(r"\1", line_text)
            N10X.Editor.SetLine(line_index, new_line)

    N10X.Editor.EndTextUpdate()
    N10X.Editor.PopUndoGroup()


# ========================================================================
# MARKDOWN TABLE FORMATTER
# ========================================================================
def FormatMarkdownTables(silent_if_outside=False):
    if not N10X.Editor.TextEditorHasFocus():
        return

    _, current_y = N10X.Editor.GetCursorPos()
    line_count = N10X.Editor.GetLineCount()

    current_line_text = N10X.Editor.GetLine(current_y).strip()
    if not (current_line_text.startswith('|') and current_line_text.endswith('|')):
        if not silent_if_outside:
            N10X.Editor.SetStatusBarText("Not inside a Markdown table block.")
        return

    # --- Phase 1: Find Table Boundaries ---
    start_y = current_y
    while start_y > 0:
        prev_line = N10X.Editor.GetLine(start_y - 1).strip()
        if not (prev_line.startswith('|') and prev_line.endswith('|')):
            break
        start_y -= 1

    end_y = current_y
    while end_y < line_count - 1:
        next_line = N10X.Editor.GetLine(end_y + 1).strip()
        if not (next_line.startswith('|') and next_line.endswith('|')):
            break
        end_y += 1

    # --- Phase 2: Parse Rows Safely ---
    raw_rows = []
    is_separator_row = {}
    max_num_columns = 0

    for idx, y in enumerate(range(start_y, end_y + 1)):
        line_text = N10X.Editor.GetLine(y).strip()[1:-1]
        cells = [cell.strip() for cell in line_text.split('|')]
        
        is_sep = bool(cells) and all(bool(c) and all(ch in '-: ' for ch in c) for c in cells)
        is_separator_row[idx] = is_sep
        
        raw_rows.append(cells)
        if len(cells) > max_num_columns:
            max_num_columns = len(cells)

    max_col_widths = [3] * max_num_columns
    for idx, cells in enumerate(raw_rows):
        if len(cells) < max_num_columns:
            cells.extend([""] * (max_num_columns - len(cells)))
        if not is_separator_row[idx]:
            for col_idx, cell in enumerate(cells):
                if len(cell) > max_col_widths[col_idx]:
                    max_col_widths[col_idx] = len(cell)

    # --- Phase 3: Format and Rewrite Lines ---
    N10X.Editor.PushUndoGroup()
    N10X.Editor.BeginTextUpdate()

    for idx, y in enumerate(range(start_y, end_y + 1)):
        cells = raw_rows[idx]
        if is_separator_row[idx]:
            formatted = ["-" * (max_col_widths[col] + 2) for col in range(max_num_columns)]
        else:
            formatted = [f" {cells[col].ljust(max_col_widths[col])} " for col in range(max_num_columns)]

        N10X.Editor.SetLine(y, "|" + "|".join(formatted) + "|")

    N10X.Editor.EndTextUpdate()
    N10X.Editor.PopUndoGroup()
    N10X.Editor.SetStatusBarText("Table auto-completed and formatted!")

def OnPreSave(filename):
    if filename and filename.lower().endswith((".md", ".markdown")):
        FormatMarkdownTables(silent_if_outside=True)

N10X.Editor.AddPreFileSaveFunction(OnPreSave)


# ========================================================================
# SCROLL MARGINS
# ========================================================================
SCROLL_MARGIN = 10

def force_margins():
    if not N10X.Editor.TextEditorHasFocus():
        return

    _, cursor_y = N10X.Editor.GetCursorPos()
    scroll_top_y = N10X.Editor.GetScrollLine()
    visible_lines = N10X.Editor.GetVisibleLineCount()
    
    if visible_lines <= SCROLL_MARGIN * 2:
        return

    scroll_bottom_y = scroll_top_y + visible_lines

    if cursor_y < (scroll_top_y + SCROLL_MARGIN):
        new_scroll_top = max(0, cursor_y - SCROLL_MARGIN)
        if new_scroll_top != scroll_top_y:
            N10X.Editor.SetScrollLine(new_scroll_top)

    elif cursor_y > (scroll_bottom_y - SCROLL_MARGIN - 1):
        max_scroll = max(0, N10X.Editor.GetLineCount() - visible_lines)
        new_scroll_top = min(max_scroll, cursor_y - visible_lines + SCROLL_MARGIN + 1)
        if new_scroll_top > scroll_top_y:
            N10X.Editor.SetScrollLine(new_scroll_top)

N10X.Editor.AddCursorMovedFunction(force_margins)


# ========================================================================
# UNIFIED BRACE & BRACKET SELECTION
# ========================================================================
BRACE_MAP   = {'{': '}'}
BRACKET_MAP = {'[': ']', '(': ')'}

def _find_matching_close(start_x, start_y, open_char, close_char, line_count):
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

def _find_enclosing_pair(start_x, start_y, pair_map, line_count):
    reverse_nest = {close_c: 0 for close_c in pair_map.values()}

    for y in range(start_y, -1, -1):
        line_text = N10X.Editor.GetLine(y)
        x_start = (start_x - 1) if y == start_y else (len(line_text) - 1)
        
        for x in range(x_start, -1, -1):
            char = line_text[x]
            if char in reverse_nest:
                reverse_nest[char] += 1
            elif char in pair_map:
                close_char = pair_map[char]
                if reverse_nest[close_char] > 0:
                    reverse_nest[close_char] -= 1
                else:
                    open_pos = (x + 1, y)
                    match_pos = _find_matching_close(x + 1, y, char, close_char, line_count)
                    if match_pos and (match_pos[1], match_pos[0]) > (start_y, start_x):
                        return open_pos, match_pos, char, close_char
    return None

def _select_inside_pairs(pair_map, label):
    if not N10X.Editor.GetCurrentFilename():
        return

    start_x, start_y = N10X.Editor.GetCursorPos()
    line_count = N10X.Editor.GetLineCount()

    # Priority 1: Already inside a pair
    enclosing = _find_enclosing_pair(start_x, start_y, pair_map, line_count)
    if enclosing:
        open_pos, close_pos, open_char, close_char = enclosing
        N10X.Editor.SetSelection(open_pos, close_pos, 0)
        N10X.Editor.CenterViewAtLinePos(close_pos[1])
        N10X.Editor.SetStatusBarText(f"Selected inside current {open_char}{close_char}")
        return

    # Priority 2: Look ahead for the next opening character
    for y in range(start_y, line_count):
        line_text = N10X.Editor.GetLine(y)
        x_start = start_x if y == start_y else 0
        for x in range(x_start, len(line_text)):
            char = line_text[x]
            if char in pair_map:
                open_pos = (x + 1, y)
                close_char = pair_map[char]
                close_pos = _find_matching_close(open_pos[0], open_pos[1], char, close_char, line_count)
                if close_pos:
                    N10X.Editor.SetSelection(open_pos, close_pos, 0)
                    N10X.Editor.CenterViewAtLinePos(close_pos[1])
                    N10X.Editor.SetStatusBarText(f"Selected next upcoming {char}{close_char}")
                else:
                    N10X.Editor.SetStatusBarText(f"Mismatched {label} ahead.")
                return

    N10X.Editor.SetStatusBarText(f"No {label} found inside or ahead.")

def SelectInsideNextBraces():
    _select_inside_pairs(BRACE_MAP, "braces")

def SelectInsideNextBrackets():
    _select_inside_pairs(BRACKET_MAP, "brackets")


# ========================================================================
# LINE & PARAGRAPH NAVIGATION / SELECTION
# ========================================================================
def CopyEntireSelectedLines():
    start_pos = N10X.Editor.GetSelectionStart()
    end_pos = N10X.Editor.GetSelectionEnd()
    orig_cursor = N10X.Editor.GetCursorPos()

    start_y = min(start_pos[1], end_pos[1])
    end_y = max(start_pos[1], end_pos[1])

    last_line_len = len(N10X.Editor.GetLine(end_y).rstrip('\r\n'))
    N10X.Editor.SetSelection((0, start_y), (last_line_len, end_y), 0)
    N10X.Editor.ExecuteCommand("Copy")
    
    N10X.Editor.SetSelection(start_pos, end_pos, 0)
    N10X.Editor.SetCursorPos(orig_cursor)

    total_lines = (end_y - start_y) + 1
    N10X.Editor.SetStatusBarText(f"Copied {total_lines} full line(s) to clipboard.")

def HighlightCurrentLine():
    _, line_index = N10X.Editor.GetCursorPos()
    line_text = N10X.Editor.GetLine(line_index)
    line_length = len(line_text.rstrip('\r\n')) if line_text else 0
    N10X.Editor.SetSelection((0, line_index), (line_length, line_index))

def MoveCursorParagraphUp():
    if not N10X.Editor.TextEditorHasFocus():
        return
    _, current_y = N10X.Editor.GetCursorPos()
    if current_y <= 0:
        return

    target_y = 0
    inside_current_block = True

    for y in range(current_y - 1, -1, -1):
        line_text = N10X.Editor.GetLine(y).strip()
        if inside_current_block:
            if not line_text:
                inside_current_block = False
        elif line_text:
            target_y = y
            break

    N10X.Editor.SetCursorPos((0, target_y))
    N10X.Editor.ScrollCursorIntoView()

def MoveCursorParagraphDown():
    if not N10X.Editor.TextEditorHasFocus():
        return
    _, current_y = N10X.Editor.GetCursorPos()
    line_count = N10X.Editor.GetLineCount()
    if current_y >= line_count - 1:
        return

    target_y = line_count - 1
    inside_current_block = True

    for y in range(current_y + 1, line_count):
        line_text = N10X.Editor.GetLine(y).strip()
        if inside_current_block:
            if not line_text:
                inside_current_block = False
        elif line_text:
            target_y = y
            break

    N10X.Editor.SetCursorPos((0, target_y))
    N10X.Editor.ScrollCursorIntoView()

def SelectParagraph():
    if not N10X.Editor.TextEditorHasFocus():
        return
    
    _, cy = N10X.Editor.GetCursorPos()
    line_count = N10X.Editor.GetLineCount()
    if not N10X.Editor.GetLine(cy).strip():
        return

    target_up_y = 0
    for y in range(cy - 1, -1, -1):
        if not N10X.Editor.GetLine(y).strip():
            target_up_y = y + 1
            break

    target_down_y = line_count - 1
    for y in range(cy + 1, line_count):
        if not N10X.Editor.GetLine(y).strip():
            target_down_y = y - 1
            break

    last_line_length = len(N10X.Editor.GetLine(target_down_y).rstrip('\r\n'))
    N10X.Editor.SetSelection((0, target_up_y), (last_line_length, target_down_y), cursor_index=0)


# ========================================================================
# WORKSPACE ROOT SEARCH (TODO / FIXME)
# ========================================================================
def _handle_workspace_tag_search(results, truncated, tag_name):
    N10X.Editor.ClearBuildOutput()
    N10X.Editor.ShowBuildOutput()

    workspace_path = N10X.Editor.GetWorkspaceFilename()
    if not workspace_path:
        N10X.Editor.LogToBuildOutput("Error: No workspace currently open.\n")
        return

    root_folder = os.path.normcase(os.path.normpath(os.path.dirname(workspace_path)))
    root_results = [
        item for item in (results or [])
        if os.path.normcase(os.path.normpath(os.path.dirname(item[0]))) == root_folder
    ]

    if not root_results:
        N10X.Editor.LogToBuildOutput(f"=== No {tag_name}s found in the root folder ===\n")
        N10X.Editor.SetStatusBarText(f"{tag_name} Search: 0 matches found in root.")
        return

    N10X.Editor.LogToBuildOutput(f"=== Root {tag_name}s ({len(root_results)} found) ===\n")
    for filename, _, line_index, line_text in root_results:
        N10X.Editor.LogToBuildOutput(f"{filename}({line_index + 1}): info: {line_text.strip()}\n")

    if truncated:
        N10X.Editor.LogToBuildOutput("\n... [Warning: Results truncated by search limit] ...\n")
        
    N10X.Editor.LogToBuildOutput("=== Scan Completed ===\n")
    N10X.Editor.ParseBuildOutput()
    N10X.Editor.SetStatusBarText(f"{tag_name} Search complete. Found {len(root_results)} items.")

def OnTodoSearchFinished(results, truncated):
    _handle_workspace_tag_search(results, truncated, "TODO")

def OnFixmeSearchFinished(results, truncated):
    _handle_workspace_tag_search(results, truncated, "FIXME")

def ListTodos():
    N10X.Editor.SetStatusBarText("Searching root workspace for TODOs...")
    N10X.Editor.FindTextInFiles("TODO:", OnTodoSearchFinished, False, False, False)

def ListFix():
    N10X.Editor.SetStatusBarText("Searching root workspace for FIXMEs...")
    N10X.Editor.FindTextInFiles("FIXME:", OnFixmeSearchFinished, False, False, False)


# ========================================================================
# WORD & NUMBER MANIPULATION
# ========================================================================
def DeleteWord():
    if not N10X.Editor.TextEditorHasFocus():
        return
    N10X.Editor.PushUndoGroup()
    N10X.Editor.ExecuteCommand("SelectCurrentWord")
    N10X.Editor.ExecuteCommand("Delete")
    N10X.Editor.PopUndoGroup()

def IncrementList():
    """
    Increments numbers under all active cursors starting from the top-most cursor's number.
    Handles numbers of any digit length cleanly via synchronous line updates.
    """
    cursor_count = N10X.Editor.GetCursorCount()
    if cursor_count < 1:
        return

    cursors = [N10X.Editor.GetCursorPos(i) for i in range(cursor_count)]
    # Sort strictly top-to-bottom, left-to-right
    cursors.sort(key=lambda p: (p[1], p[0]))

    def _find_num_at(x, y):
        line = N10X.Editor.GetLine(y)
        if not line:
            return None
        for m in RE_NUMBER.finditer(line):
            if m.start() <= x <= m.end():
                return int(m.group()), m.start(), m.end()
        return None

    first_match = _find_num_at(cursors[0][0], cursors[0][1])
    if not first_match:
        N10X.Editor.SetStatusBarText("IncrementList: First cursor must be on a number.")
        return

    start_val = first_match[0]

    # Collect replacements per line
    line_edits = {}
    for idx, (cx, cy) in enumerate(cursors):
        match = _find_num_at(cx, cy)
        if match:
            _, s_col, e_col = match
            line_edits.setdefault(cy, []).append((s_col, e_col, str(start_val + idx)))

    N10X.Editor.PushUndoGroup()
    N10X.Editor.BeginTextUpdate()

    for y, edits in line_edits.items():
        line = N10X.Editor.GetLine(y)
        # Apply right-to-left on the same line so column indices don't shift
        for s_col, e_col, replacement in sorted(edits, key=lambda item: item[0], reverse=True):
            line = line[:s_col] + replacement + line[e_col:]
        N10X.Editor.SetLine(y, line)

    N10X.Editor.EndTextUpdate()
    N10X.Editor.PopUndoGroup()

def TransposeWords():
    if not N10X.Editor.TextEditorHasFocus():
        return
        
    x, y = N10X.Editor.GetCursorPos()
    line = N10X.Editor.GetLine(y)
    if not line:
        return

    matches = [(m.start(), m.end(), m.group()) for m in RE_WORDS.finditer(line)]
    if len(matches) < 2:
        return

    word1_idx = -1
    for i, (start, end, _) in enumerate(matches):
        if end >= x:
            word1_idx = (0 if i == 0 else i - 1) if x <= start else i
            break
            
    if word1_idx == -1 or word1_idx == len(matches) - 1:
        word1_idx = len(matches) - 2
    if word1_idx < 0:
        return
        
    w1_start, w1_end, w1_text = matches[word1_idx]
    w2_start, w2_end, w2_text = matches[word1_idx + 1]
    
    separator = line[w1_end:w2_start]
    transposed = w2_text + separator + w1_text
    new_line = line[:w1_start] + transposed + line[w2_end:]

    N10X.Editor.PushUndoGroup()
    N10X.Editor.SetLine(y, new_line)
    N10X.Editor.SetCursorPos((w1_start + len(transposed), y))
    N10X.Editor.PopUndoGroup()


# ========================================================================
# COLUMN AUTO-RESIZE (65/35 Split)
# ========================================================================
_last_active_column = -1
_auto_resize_enabled = False

def ToggleAutoResizeMode():
    global _auto_resize_enabled, _last_active_column
    _auto_resize_enabled = not _auto_resize_enabled
    if _auto_resize_enabled:
        _last_active_column = -1 
        N10X.Editor.SetStatusBarText("Auto-Resize Mode: ON (65/35)")
    else:
        N10X.Editor.SetStatusBarText("Auto-Resize Mode: OFF")

def OnUpdateAutoResizeColumns():
    if not _auto_resize_enabled:
        return

    global _last_active_column
    pos = N10X.Editor.GetCurrentPanelGridPos()
    if not pos:
        return
        
    active_column = pos[0]
    if active_column != _last_active_column:
        _last_active_column = active_column
        try:
            total_width = N10X.Editor.GetColumnWidth(0) + N10X.Editor.GetColumnWidth(1)
            if total_width > 0:
                w_large = int(total_width * 0.65)
                w_small = total_width - w_large
                if active_column == 0:
                    N10X.Editor.SetColumnWidth(0, w_large)
                    N10X.Editor.SetColumnWidth(1, w_small)
                elif active_column == 1:
                    N10X.Editor.SetColumnWidth(0, w_small)
                    N10X.Editor.SetColumnWidth(1, w_large)
        except Exception:
            pass

N10X.Editor.AddUpdateFunction(OnUpdateAutoResizeColumns)


# ========================================================================
# CUSTOM SYNTAX COMMENT TOGGLING (.2if / .uflex2f)
# ========================================================================
def ToggleUflex2fComment():
    N10X.Editor.PushUndoGroup()
    N10X.Editor.BeginTextUpdate()
    
    lines_to_toggle = _get_unique_cursor_lines()
        
    all_commented = True
    for y in lines_to_toggle:
        line = N10X.Editor.GetLine(y)
        if line is not None:
            stripped = line.lstrip()
            if stripped and not stripped.startswith('#'):
                all_commented = False
                break

    for y in lines_to_toggle:
        line = N10X.Editor.GetLine(y)
        if not line or not line.strip():
            continue
            
        if all_commented:
            idx = line.find('#')
            if idx != -1:
                remove_len = 2 if (idx + 1 < len(line) and line[idx + 1] == ' ') else 1
                N10X.Editor.SetLine(y, line[:idx] + line[idx + remove_len:])
        else:
            indent_len = len(line) - len(line.lstrip())
            N10X.Editor.SetLine(y, line[:indent_len] + "# " + line[indent_len:])

    N10X.Editor.EndTextUpdate()
    N10X.Editor.PopUndoGroup()

def OnInterceptCommand(command):
    if command == "ToggleComment":
        filename = N10X.Editor.GetCurrentFilename()
        if filename and filename.lower().endswith((".2if", ".uflex2f")):
            ToggleUflex2fComment()
            return True
    return False

N10X.Editor.AddInterceptCommandFunction(OnInterceptCommand)

# ========================================================================
# SMART TABLE & EXPRESSION ALIGNMENT (USING TEMP BUFFER)
# ========================================================================
import tempfile

_align_saved_state = None
_ALIGN_TEMP_PATH = os.path.normpath(os.path.join(tempfile.gettempdir(), "_10x_align_input.tmp"))
RE_NON_WS = re.compile(r"\S+")

def _is_align_temp_active():
    if _align_saved_state is None:
        return False
    cur = N10X.Editor.GetCurrentFilename()
    if not cur:
        return False
    return os.path.normcase(os.path.normpath(cur)) == os.path.normcase(_ALIGN_TEMP_PATH)

def _capture_editor_state():
    """Captures the exact file, cursor, and selection state BEFORE opening the temp file."""
    start_pos = N10X.Editor.GetSelectionStart()
    end_pos = N10X.Editor.GetSelectionEnd()
    cursor_count = N10X.Editor.GetCursorCount()
    cx, cy = N10X.Editor.GetCursorPos()
    line_count = N10X.Editor.GetLineCount()

    target_lines = None
    if start_pos != end_pos:
        start_y = min(start_pos[1], end_pos[1])
        end_y = max(start_pos[1], end_pos[1])
        if end_y > start_y and max((start_pos[1], start_pos[0]), (end_pos[1], end_pos[0]))[1] == 0:
            end_y -= 1
        target_lines = list(range(start_y, end_y + 1))
    elif cursor_count > 1:
        target_lines = _get_unique_cursor_lines()

    return {
        "filename": N10X.Editor.GetCurrentFilename(),
        "panel_pos": N10X.Editor.GetCurrentPanelGridPos(),
        "cursor_pos": (cx, cy),
        "line_count": line_count,
        "target_lines": target_lines,
    }

def _align_whitespace_columns(target_lines):
    """
    Smart column alignment for whitespace-separated tables where some lines
    have fewer tokens and are indented to sit beneath a specific column.
    """
    row_tokens = {}
    max_tokens_row = None
    max_token_count = 0

    for y in target_lines:
        line = N10X.Editor.GetLine(y)
        if line is None:
            continue
        line_clean = line.rstrip('\r\n')
        eol = line[len(line_clean):]
        # Expand tabs to spaces so visual column positions are accurate
        expanded = line_clean.expandtabs(4)
        tokens = [(m.start(), m.end(), m.group()) for m in RE_NON_WS.finditer(expanded)]
        row_tokens[y] = {"tokens": tokens, "eol": eol, "raw": line_clean}
        if len(tokens) > max_token_count:
            max_token_count = len(tokens)
            max_tokens_row = y

    if max_token_count < 2 or max_tokens_row is None:
        N10X.Editor.SetStatusBarText("Align: Not enough columns to align.")
        return 0

    # Use the row with the most tokens as the visual column anchor reference
    ref_tokens = row_tokens[max_tokens_row]["tokens"]
    base_indent = " " * ref_tokens[0][0]

    # Map each row's tokens into their corresponding table column indices
    grid = {}
    total_cols = max_token_count

    for y, data in row_tokens.items():
        tokens = data["tokens"]
        if not tokens:
            grid[y] = None
            continue

        num_tok = len(tokens)
        if num_tok == max_token_count:
            col_offset = 0
        else:
            # Find which reference column the first token on this line sits under
            first_start, first_end, _ = tokens[0]
            first_mid = (first_start + first_end) / 2.0
            best_col = min(
                range(len(ref_tokens)),
                key=lambda c: abs(((ref_tokens[c][0] + ref_tokens[c][1]) / 2.0) - first_mid)
            )
            # If the remaining tokens exactly match the tail of the table, lock to the right
            if best_col > 0 and (max_token_count - num_tok) == best_col:
                col_offset = best_col
            else:
                col_offset = best_col

        row_cells = [""] * col_offset + [t[2] for t in tokens]
        if len(row_cells) > total_cols:
            total_cols = len(row_cells)
        grid[y] = row_cells

    # Pad all rows to total_cols and compute maximum width per column
    col_widths = [0] * total_cols
    for y, cells in grid.items():
        if cells is None:
            continue
        while len(cells) < total_cols:
            cells.append("")
        for c_idx, text in enumerate(cells):
            if len(text) > col_widths[c_idx]:
                col_widths[c_idx] = len(text)

    # Rewrite lines with clean 2-space column gutters
    N10X.Editor.PushUndoGroup()
    N10X.Editor.BeginTextUpdate()

    aligned_count = 0
    col_gap = "  "

    for y in target_lines:
        cells = grid.get(y)
        if not cells:
            continue
        eol = row_tokens[y]["eol"]
        padded = [cells[c].ljust(col_widths[c]) for c in range(total_cols)]
        new_line = base_indent + col_gap.join(padded).rstrip(' ') + eol
        N10X.Editor.SetLine(y, new_line)
        aligned_count += 1

    N10X.Editor.EndTextUpdate()
    N10X.Editor.PopUndoGroup()
    return aligned_count

def _perform_alignment(expr, state):
    """Executes either smart whitespace column alignment or delimiter alignment."""
    cur_file = N10X.Editor.GetCurrentFilename()
    if not cur_file or os.path.normcase(os.path.normpath(cur_file)) != os.path.normcase(os.path.normpath(state["filename"])):
        N10X.Editor.FocusFile(state["filename"])
        N10X.Editor.CallOnMainThread(lambda: _perform_alignment(expr, state))
        return

    cx, cy = state["cursor_pos"]
    line_count = N10X.Editor.GetLineCount()
    target_lines = state["target_lines"]

    # Check if user requested Smart Whitespace Table Alignment (empty input or spaces)
    is_whitespace_mode = (expr.strip() == "")

    if target_lines is None:
        if is_whitespace_mode:
            # Auto-detect contiguous non-empty lines around cursor
            if not (N10X.Editor.GetLine(cy) or "").strip():
                N10X.Editor.SetStatusBarText("Align: Current line is empty.")
                return
            start_y = cy
            while start_y > 0 and (N10X.Editor.GetLine(start_y - 1) or "").strip():
                start_y -= 1
            end_y = cy
            while end_y < line_count - 1 and (N10X.Editor.GetLine(end_y + 1) or "").strip():
                end_y += 1
            target_lines = list(range(start_y, end_y + 1))
        else:
            if expr not in (N10X.Editor.GetLine(cy) or ""):
                N10X.Editor.SetStatusBarText(f"Align: '{expr}' not found on line {cy + 1}.")
                return
            start_y = cy
            while start_y > 0 and expr in (N10X.Editor.GetLine(start_y - 1) or ""):
                start_y -= 1
            end_y = cy
            while end_y < line_count - 1 and expr in (N10X.Editor.GetLine(end_y + 1) or ""):
                end_y += 1
            target_lines = list(range(start_y, end_y + 1))

    if len(target_lines) < 2:
        N10X.Editor.SetStatusBarText("Align: Requires at least 2 lines.")
        return

    # --- MODE 1: Smart Whitespace Table Alignment ---
    if is_whitespace_mode:
        count = _align_whitespace_columns(target_lines)
        N10X.Editor.SetCursorPos((cx, cy))
        if count:
            N10X.Editor.SetStatusBarText(f"Smart-aligned {count} lines into columns.")
        return

    # --- MODE 2: Explicit Delimiter Alignment ---
    parsed_rows = {}
    max_cols = 0

    for y in target_lines:
        line = N10X.Editor.GetLine(y)
        if line is None:
            continue
        line_clean = line.rstrip('\r\n')
        eol = line[len(line_clean):]

        if expr in line_clean:
            raw_parts = line_clean.split(expr)
            cells = [raw_parts[0].rstrip(' \t')] + [p.strip(' \t') for p in raw_parts[1:]]
            parsed_rows[y] = {"has_expr": True, "cells": cells, "eol": eol}
            if len(cells) > max_cols:
                max_cols = len(cells)
        else:
            parsed_rows[y] = {"has_expr": False, "raw": line_clean, "eol": eol}

    if max_cols < 2:
        N10X.Editor.SetStatusBarText(f"Align: '{expr}' not found in selection.")
        return

    col_widths = [0] * (max_cols - 1)
    for y, row in parsed_rows.items():
        if row["has_expr"]:
            cells = row["cells"]
            for i in range(len(cells) - 1):
                if len(cells[i]) > col_widths[i]:
                    col_widths[i] = len(cells[i])

    N10X.Editor.PushUndoGroup()
    N10X.Editor.BeginTextUpdate()

    aligned_count = 0
    sep_before = "" if expr in (",", ";") else " "
    joiner = f"{sep_before}{expr} "

    for y in target_lines:
        row = parsed_rows.get(y)
        if not row or not row["has_expr"]:
            continue
        cells = row["cells"]
        num_cells = len(cells)
        formatted_parts = [
            cells[i].ljust(col_widths[i]) if i < num_cells - 1 else cells[i]
            for i in range(num_cells)
        ]
        new_line = joiner.join(formatted_parts).rstrip(' \t') + row["eol"]
        N10X.Editor.SetLine(y, new_line)
        aligned_count += 1

    N10X.Editor.EndTextUpdate()
    N10X.Editor.PopUndoGroup()
    N10X.Editor.SetCursorPos((cx, cy))
    N10X.Editor.SetStatusBarText(f"Aligned {aligned_count} lines by '{expr}'.")

def _finish_temp_align(cancel=False):
    """Reads the expression from the temp file, closes it, and schedules alignment."""
    global _align_saved_state
    state = _align_saved_state
    _align_saved_state = None

    expr = ""
    if not cancel:
        # Read line 2 (index 1) directly so space/empty input works for whitespace mode
        if N10X.Editor.GetLineCount() > 1:
            expr = (N10X.Editor.GetLine(1) or "").rstrip('\r\n')

    N10X.Editor.DiscardUnsavedChanges()
    N10X.Editor.CloseFile()

    if not state or not state["filename"]:
        return

    N10X.Editor.OpenFile(state["filename"], state["panel_pos"], state["cursor_pos"])

    if cancel:
        N10X.Editor.SetStatusBarText("Align cancelled.")
    else:
        N10X.Editor.CallOnMainThread(lambda: _perform_alignment(expr, state))

def _on_align_temp_key(key, shift, control, alt):
    if not _is_align_temp_active():
        return False

    if key in ("Return", "Enter"):
        N10X.Editor.CallOnMainThread(lambda: _finish_temp_align(cancel=False))
        return True
    elif key == "Escape":
        N10X.Editor.CallOnMainThread(lambda: _finish_temp_align(cancel=True))
        return True

    return False

def AlignByTempFile():
    """
    Opens a temporary input buffer in 10x.
    - Press Enter immediately (or type Space + Enter) for Smart Whitespace Column Alignment.
    - Type a character/string (e.g., =, ,, //) and press Enter for Delimiter Alignment.
    """
    global _align_saved_state
    if not N10X.Editor.TextEditorHasFocus():
        return

    cur_file = N10X.Editor.GetCurrentFilename()
    if not cur_file:
        return

    _align_saved_state = _capture_editor_state()

    with open(_ALIGN_TEMP_PATH, "w", encoding="utf-8") as f:
        f.write("# Leave line 2 blank (or type Space) and hit Enter for Smart Whitespace Table Align, or type a delimiter:\n")
        f.write("")

    N10X.Editor.OpenFile(_ALIGN_TEMP_PATH, _align_saved_state["panel_pos"], (0, 1))
    N10X.Editor.SetStatusBarText("Align: Press Enter for Smart Whitespace Table, or type delimiter + Enter")

N10X.Editor.AddOnInterceptKeyFunction(_on_align_temp_key)