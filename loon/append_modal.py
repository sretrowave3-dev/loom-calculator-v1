with open("control_pad.c", "a", encoding="utf-8") as f:
    f.write("""
// --- MODAL RESULT WINDOW PROCEDURE ---
LRESULT CALLBACK ModalWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
        case WM_PAINT: {
            PAINTSTRUCT ps;
            HDC hdc = BeginPaint(hwnd, &ps);
            RECT rc; GetClientRect(hwnd, &rc);
            
            HBRUSH bgBrush = CreateSolidBrush(RGB(20, 24, 34));
            FillRect(hdc, &rc, bgBrush);
            DeleteObject(bgBrush);
            
            HFONT hFontBig = CreateFontA(24, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, DEFAULT_QUALITY, DEFAULT_PITCH, "Segoe UI");
            HFONT hFontBold = CreateFontA(16, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, DEFAULT_QUALITY, DEFAULT_PITCH, "Segoe UI");
            HFONT hFontNormal = CreateFontA(14, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, DEFAULT_QUALITY, DEFAULT_PITCH, "Segoe UI");
            
            SetBkMode(hdc, TRANSPARENT);
            
            // Draw close button
            SelectObject(hdc, hFontBold);
            SetTextColor(hdc, RGB(180, 180, 180));
            TextOutA(hdc, rc.right - 25, 10, "X", 1);
            
            // Draw result
            SelectObject(hdc, hFontBig);
            if (strcmp(g_state.modal_type, "warning") == 0) {
                SetTextColor(hdc, RGB(255, 180, 50));
            } else {
                SetTextColor(hdc, RGB(50, 255, 180)); // Cyan/Green
            }
            char res_buf[550];
            snprintf(res_buf, sizeof(res_buf), "Result: %s", g_state.modal_result);
            TextOutA(hdc, 20, 20, res_buf, strlen(res_buf));
            
            // Details
            SelectObject(hdc, hFontBold);
            SetTextColor(hdc, RGB(200, 200, 200));
            TextOutA(hdc, 20, 70, "Input Query:", 12);
            SelectObject(hdc, hFontNormal);
            TextOutA(hdc, 130, 70, g_state.modal_query, strlen(g_state.modal_query));
            
            SelectObject(hdc, hFontBold);
            TextOutA(hdc, 20, 100, "Method:", 7);
            SelectObject(hdc, hFontNormal);
            TextOutA(hdc, 130, 100, g_state.modal_method, strlen(g_state.modal_method));
            
            SelectObject(hdc, hFontBold);
            TextOutA(hdc, 20, 130, "Status / Tip:", 13);
            SelectObject(hdc, hFontNormal);
            SetTextColor(hdc, RGB(255, 180, 50));
            TextOutA(hdc, 130, 130, g_state.modal_status, strlen(g_state.modal_status));
            
            DeleteObject(hFontBig);
            DeleteObject(hFontBold);
            DeleteObject(hFontNormal);
            EndPaint(hwnd, &ps);
            break;
        }
        case WM_LBUTTONDOWN: {
            int x = LOWORD(lParam);
            int y = HIWORD(lParam);
            RECT rc; GetClientRect(hwnd, &rc);
            if (x > rc.right - 30 && y < 30) {
                ShowWindow(hwnd, SW_HIDE);
                g_state.show_modal = 0;
            }
            break;
        }
        case WM_KEYDOWN:
            if (wParam == VK_ESCAPE) {
                ShowWindow(hwnd, SW_HIDE);
                g_state.show_modal = 0;
            }
            break;
        case WM_CLOSE:
            ShowWindow(hwnd, SW_HIDE);
            g_state.show_modal = 0;
            return 0;
        default:
            return DefWindowProcA(hwnd, msg, wParam, lParam);
    }
    return 0;
}
""")
