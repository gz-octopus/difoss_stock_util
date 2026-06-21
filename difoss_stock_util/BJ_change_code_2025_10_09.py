from typing import Optional

__all__ = [
    'change_date',
    'BJ_changes_start_with',
    'old_2_new',
]

change_date = "2025-10-09"

BJ_changes_start_with = ('87', '83', '43')

# -----------------------------------------------------------------------------------
def old_2_new(code: str) -> str:    
    if len(code) == 6 and code.startswith(BJ_changes_start_with):
        code = '920' + code[3:]
    return code
