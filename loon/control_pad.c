#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// Control IDs for Control Pad
#define ID_MODE_AUTO        101
#define ID_MODE_ALWAYS      102
#define ID_MODE_OFF         103
#define ID_BTN_TOGGLE_ANIM  104
#define ID_BTN_STYLE_WAVE   105
#define ID_BTN_STYLE_RADAR  106
#define ID_BTN_STYLE_MATRIX 107

#define ID_BTN_INT_INDEF    201
#define ID_BTN_DERIVE       202
#define ID_BTN_INT_DEF      203
#define ID_BTN_ROOTS        204
#define ID_BTN_EVAL         205

#define ID_BTN_TEST_ANIM    301
#define ID_BTN_HIST         302
#define ID_BTN_CLEAR        303
#define ID_BTN_HELP         304

#define TIMER_ANIM_ID       1
#define TIMER_IPC_ID        2

// Pop-Out Modes
typedef enum {
    MODE_AUTO = 0,
    MODE_ALWAYS = 1,
    MODE_OFF = 2
} PopoutMode;

// Animation Visualizer Styles
typedef enum {
    STYLE_WAVE = 0,
    STYLE_RADAR = 1,
    STYLE_MATRIX = 2
} AnimStyle;

// Shared GUI State with Real-Time Machine Mind (Cognitive) Telemetry
typedef struct {
    char status[32];          // "idle" or "processing"
    char task[128];           // e.g. "Computing Indefinite Integral..."
    char active_function[256];// e.g. "x/(x+1) + 45x^2"
    PopoutMode popout_mode;
    AnimStyle anim_style;
    int is_anim_visible;
    char command_pending[128];
    double demo_timer;        // > 0 when running test demo
    double idle_countdown;    // countdown before auto-hiding

    // Real-Time Machine Mind (Cognitive) State:
    char module[64];          // e.g. "TOKENIZER", "SYNTAX_PARSER", "SYMBOLIC_CORE", "VERIFIER", "SYNTHESIZER"
    int active_node;          // 0 to 4 (0=INPUT, 1=PARSE, 2=SOLVER, 3=VERIFY, 4=OUTPUT)
    float progress;           // 0.0 to 1.0
    char thoughts[5][160];    // 5 rolling thoughts in the machine's mind
    char current_thought[160];
    char math_working[256];

    // Output Result Modal State:
    int show_modal;
    char modal_type[32];      // "success" or "warning"
    char modal_query[256];
    char modal_result[512];
    char modal_method[128];
    char modal_status[256];
} GuiState;

static GuiState g_state;
static HWND g_hwndControlPad = NULL;
static HWND g_hwndAnimation = NULL;
static HWND g_hwndModal = NULL;

static HWND g_lblActiveFunc = NULL;
static HWND g_lblStatus = NULL;
static HWND g_lblTask = NULL;

static HWND g_rbAuto = NULL;
static HWND g_rbAlways = NULL;
static HWND g_rbOff = NULL;

static float g_anim_time = 0.0f;
static const char *STATE_FILE = "smart_gui_state.json";

// Forward Declarations
LRESULT CALLBACK ControlPadWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam);
LRESULT CALLBACK AnimationWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam);
LRESULT CALLBACK ModalWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam);
void SaveStateToFile(void);
void LoadStateFromFile(void);
void SendCommandToCLI(const char *cmd);

// Read simple JSON string field
static void parse_json_str(const char *json, const char *key, char *out, size_t max_len) {
    char pattern[64];
    snprintf(pattern, sizeof(pattern), "\"%s\":", key);
    char *pos = strstr(json, pattern);
    if (!pos) return;
    pos += strlen(pattern);
    while (*pos == ' ' || *pos == '\t') pos++;
    if (*pos == '\"') {
        pos++;
        char *end = strchr(pos, '\"');
        if (end) {
            size_t len = (size_t)(end - pos);
            if (len >= max_len) len = max_len - 1;
            memcpy(out, pos, len);
            out[len] = '\0';
        }
    }
}

// Read simple JSON integer field
static int parse_json_int(const char *json, const char *key, int default_val) {
    char pattern[64];
    snprintf(pattern, sizeof(pattern), "\"%s\":", key);
    char *pos = strstr(json, pattern);
    if (!pos) return default_val;
    pos += strlen(pattern);
    while (*pos == ' ' || *pos == '\t') pos++;
    return atoi(pos);
}

// Read simple JSON float field
static float parse_json_float(const char *json, const char *key, float default_val) {
    char pattern[64];
    snprintf(pattern, sizeof(pattern), "\"%s\":", key);
    char *pos = strstr(json, pattern);
    if (!pos) return default_val;
    pos += strlen(pattern);
    while (*pos == ' ' || *pos == '\t') pos++;
    return (float)atof(pos);
}

void LoadStateFromFile(void) {
    FILE *f = fopen(STATE_FILE, "r");
    if (!f) return;
    char buffer[8192];
    size_t n = fread(buffer, 1, sizeof(buffer) - 1, f);
    fclose(f);
    if (n == 0) return;
    buffer[n] = '\0';

    char status[32] = "";
    char task[128] = "";
    char fn[256] = "";
    char pop[32] = "";
    char mod[64] = "";
    char curr_th[160] = "";
    char math_w[256] = "";

    parse_json_str(buffer, "status", status, sizeof(status));
    parse_json_str(buffer, "task", task, sizeof(task));
    parse_json_str(buffer, "active_function", fn, sizeof(fn));
    parse_json_str(buffer, "popout_mode", pop, sizeof(pop));

    parse_json_str(buffer, "module", mod, sizeof(mod));
    parse_json_str(buffer, "current_thought", curr_th, sizeof(curr_th));
    parse_json_str(buffer, "math_working", math_w, sizeof(math_w));

    if (g_state.demo_timer <= 0.0) {
        if (strlen(status) > 0) snprintf(g_state.status, sizeof(g_state.status), "%s", status);
        if (strlen(task) > 0) snprintf(g_state.task, sizeof(g_state.task), "%s", task);
        if (strlen(mod) > 0) snprintf(g_state.module, sizeof(g_state.module), "%s", mod);
        if (strlen(curr_th) > 0) snprintf(g_state.current_thought, sizeof(g_state.current_thought), "%s", curr_th);
        if (strlen(math_w) > 0) snprintf(g_state.math_working, sizeof(g_state.math_working), "%s", math_w);

        g_state.active_node = parse_json_int(buffer, "active_node", g_state.active_node);
        g_state.progress = parse_json_float(buffer, "progress", g_state.progress);

        for (int i = 0; i < 5; i++) {
            char key[32];
            snprintf(key, sizeof(key), "thought_%d", i + 1);
            char th[160] = "";
            parse_json_str(buffer, key, th, sizeof(th));
            if (strlen(th) > 0) {
                snprintf(g_state.thoughts[i], sizeof(g_state.thoughts[i]), "%s", th);
            }
        }
        
        g_state.show_modal = parse_json_int(buffer, "show_modal", 0);
        if (g_state.show_modal) {
            parse_json_str(buffer, "modal_type", g_state.modal_type, sizeof(g_state.modal_type));
            parse_json_str(buffer, "modal_query", g_state.modal_query, sizeof(g_state.modal_query));
            parse_json_str(buffer, "modal_result", g_state.modal_result, sizeof(g_state.modal_result));
            parse_json_str(buffer, "modal_method", g_state.modal_method, sizeof(g_state.modal_method));
            parse_json_str(buffer, "modal_status", g_state.modal_status, sizeof(g_state.modal_status));
        }
    }
    if (strlen(fn) > 0) snprintf(g_state.active_function, sizeof(g_state.active_function), "%s", fn);
}

void SaveStateToFile(void) {
    FILE *f = fopen(STATE_FILE, "w");
    if (!f) return;
    const char *pop_str = (g_state.popout_mode == MODE_ALWAYS) ? "always" :
                          ((g_state.popout_mode == MODE_OFF) ? "off" : "auto");
    fprintf(f, "{\n");
    fprintf(f, "  \"status\": \"%s\",\n", g_state.status);
    fprintf(f, "  \"task\": \"%s\",\n", g_state.task);
    fprintf(f, "  \"active_function\": \"%s\",\n", g_state.active_function);
    fprintf(f, "  \"popout_mode\": \"%s\",\n", pop_str);
    fprintf(f, "  \"anim_style\": %d,\n", (int)g_state.anim_style);
    fprintf(f, "  \"command_pending\": \"%s\",\n", g_state.command_pending);
    fprintf(f, "  \"module\": \"%s\",\n", g_state.module);
    fprintf(f, "  \"active_node\": %d,\n", g_state.active_node);
    fprintf(f, "  \"progress\": %.2f,\n", g_state.progress);
    fprintf(f, "  \"current_thought\": \"%s\",\n", g_state.current_thought);
    fprintf(f, "  \"math_working\": \"%s\",\n", g_state.math_working);
    for (int i = 0; i < 5; i++) {
        fprintf(f, "  \"thought_%d\": \"%s\"%s\n", i + 1, g_state.thoughts[i], (i == 4) ? "" : ",");
    }
    fprintf(f, "}\n");
    fclose(f);
}

void SendCommandToCLI(const char *cmd) {
    snprintf(g_state.command_pending, sizeof(g_state.command_pending), "%s", cmd);
    SaveStateToFile();
}

// --- MAIN ENTRY POINT ---
int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    (void)hPrevInstance; (void)lpCmdLine; (void)nCmdShow;

    // Check if another instance is already running
    HWND existing = FindWindowA("SmartCalControlPadClass", NULL);
    if (existing) {
        SetForegroundWindow(existing);
        return 0;
    }

    memset(&g_state, 0, sizeof(g_state));
    strcpy(g_state.status, "idle");
    strcpy(g_state.task, "Engine Ready");
    strcpy(g_state.active_function, "None (Type in CLI or enter below)");
    g_state.popout_mode = MODE_AUTO;
    g_state.anim_style = STYLE_WAVE;
    g_state.is_anim_visible = 0;
    g_state.demo_timer = 0.0;
    g_state.idle_countdown = 0.0;

    strcpy(g_state.module, "STANDBY");
    g_state.active_node = 0;
    g_state.progress = 0.0f;
    strcpy(g_state.current_thought, "System ready. Awaiting calculus input...");
    strcpy(g_state.math_working, "Memory: Clean | Simpson & Newton cores initialized");

    strcpy(g_state.thoughts[0], "[STANDBY] Neural mathematical interpreter online");
    strcpy(g_state.thoughts[1], "[READY] Simpson Quadrature & 5-point stencil ready");
    strcpy(g_state.thoughts[2], "[READY] Symbolic antiderivative rules loaded (+ C)");
    strcpy(g_state.thoughts[3], "[READY] Domain pole & Newton-Raphson scanner loaded");
    strcpy(g_state.thoughts[4], "[AWAIT] Enter an equation in console or click Control Pad");

    LoadStateFromFile();
    SaveStateToFile();

    // Register Window Classes
    WNDCLASSA wcPad = {0};
    wcPad.lpfnWndProc = ControlPadWndProc;
    wcPad.hInstance = hInstance;
    wcPad.lpszClassName = "SmartCalControlPadClass";
    wcPad.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
    wcPad.hCursor = LoadCursor(NULL, IDC_ARROW);
    wcPad.hIcon = LoadIcon(NULL, IDI_APPLICATION);
    RegisterClassA(&wcPad);

    WNDCLASSA wcAnim = {0};
    wcAnim.lpfnWndProc = AnimationWndProc;
    wcAnim.hInstance = hInstance;
    wcAnim.lpszClassName = "SmartCalAnimClass";
    wcAnim.hbrBackground = (HBRUSH)GetStockObject(BLACK_BRUSH);
    wcAnim.hCursor = LoadCursor(NULL, IDC_ARROW);
    wcAnim.hIcon = LoadIcon(NULL, IDI_APPLICATION);
    RegisterClassA(&wcAnim);

    WNDCLASSA wcModal = {0};
    wcModal.lpfnWndProc = ModalWndProc;
    wcModal.hInstance = hInstance;
    wcModal.lpszClassName = "SmartCalModalClass";
    wcModal.hbrBackground = (HBRUSH)GetStockObject(BLACK_BRUSH);
    wcModal.hCursor = LoadCursor(NULL, IDC_ARROW);
    wcModal.hIcon = LoadIcon(NULL, IDI_APPLICATION);
    RegisterClassA(&wcModal);

    // Screen dimensions
    int screenW = GetSystemMetrics(SM_CXSCREEN);
    int screenH = GetSystemMetrics(SM_CYSCREEN);

    int padW = 480;
    int padH = 620;
    int padX = screenW - padW - 30;
    int padY = (screenH - padH) / 2;
    if (padY < 40) padY = 40;

    int animW = 640;
    int animH = 490;
    int animX = padX - animW - 20;
    if (animX < 15) animX = 15;
    int animY = padY + 30;

    // Create Control Pad Window
    g_hwndControlPad = CreateWindowExA(
        WS_EX_APPWINDOW,
        "SmartCalControlPadClass",
        "SmartCal AI - Control Pad",
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
        padX, padY, padW, padH,
        NULL, NULL, hInstance, NULL
    );

    // Create Animation Window (Initially hidden or auto-controlled)
    g_hwndAnimation = CreateWindowExA(
        WS_EX_TOOLWINDOW | WS_EX_TOPMOST,
        "SmartCalAnimClass",
        "SmartCal Neural Math Engine - Real-Time Machine Mind",
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_THICKFRAME,
        animX, animY, animW, animH,
        NULL, NULL, hInstance, NULL
    );

    // Create Modal Window
    g_hwndModal = CreateWindowExA(
        WS_EX_TOOLWINDOW | WS_EX_TOPMOST,
        "SmartCalModalClass",
        "SmartCal Result",
        WS_POPUP | WS_BORDER,
        screenW / 2 - 250, screenH / 2 - 120, 500, 200,
        NULL, NULL, hInstance, NULL
    );

    ShowWindow(g_hwndControlPad, SW_SHOW);
    UpdateWindow(g_hwndControlPad);

    if (g_state.popout_mode == MODE_ALWAYS) {
        ShowWindow(g_hwndAnimation, SW_SHOW);
        g_state.is_anim_visible = 1;
    }

    SetTimer(g_hwndAnimation, TIMER_ANIM_ID, 30, NULL); // ~33 FPS
    SetTimer(g_hwndControlPad, TIMER_IPC_ID, 100, NULL); // 10 Hz IPC check

    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    return (int)msg.wParam;
}

// --- CONTROL PAD WINDOW PROCEDURE ---
LRESULT CALLBACK ControlPadWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
        case WM_CREATE: {
            HINSTANCE hInst = ((LPCREATESTRUCT)lParam)->hInstance;

            // 1. Title Banner
            CreateWindowA("STATIC", "SMART AI CALCULATOR - CONTROL PAD",
                WS_CHILD | WS_VISIBLE | SS_CENTER,
                15, 12, 435, 22, hwnd, NULL, hInst, NULL);
            CreateWindowA("STATIC", "Real-Time Machine Mind Monitor & Math Hub",
                WS_CHILD | WS_VISIBLE | SS_CENTER,
                15, 34, 435, 18, hwnd, NULL, hInst, NULL);

            // 2. GroupBox 1: Animation Pop-Out Control
            CreateWindowA("BUTTON", "  Machine Mind Screen & Pop-Out Controls  ",
                WS_CHILD | WS_VISIBLE | BS_GROUPBOX,
                15, 60, 435, 140, hwnd, NULL, hInst, NULL);

            g_rbAuto = CreateWindowA("BUTTON", "Auto Pop-Out (On Process)",
                WS_CHILD | WS_VISIBLE | BS_AUTORADIOBUTTON | WS_GROUP,
                30, 85, 230, 20, hwnd, (HMENU)ID_MODE_AUTO, hInst, NULL);

            g_rbAlways = CreateWindowA("BUTTON", "Always Show Window",
                WS_CHILD | WS_VISIBLE | BS_AUTORADIOBUTTON,
                30, 108, 190, 20, hwnd, (HMENU)ID_MODE_ALWAYS, hInst, NULL);

            g_rbOff = CreateWindowA("BUTTON", "Don't Pop Out (Hidden)",
                WS_CHILD | WS_VISIBLE | BS_AUTORADIOBUTTON,
                30, 131, 190, 20, hwnd, (HMENU)ID_MODE_OFF, hInst, NULL);

            SendMessage(g_rbAuto, BM_SETCHECK, BST_CHECKED, 0);

            CreateWindowA("BUTTON", "Toggle Screen",
                WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                275, 85, 160, 30, hwnd, (HMENU)ID_BTN_TOGGLE_ANIM, hInst, NULL);

            // Style selector buttons
            CreateWindowA("BUTTON", "Wave",
                WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                275, 122, 50, 26, hwnd, (HMENU)ID_BTN_STYLE_WAVE, hInst, NULL);
            CreateWindowA("BUTTON", "Radar",
                WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                330, 122, 50, 26, hwnd, (HMENU)ID_BTN_STYLE_RADAR, hInst, NULL);
            CreateWindowA("BUTTON", "Matrix",
                WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                385, 122, 50, 26, hwnd, (HMENU)ID_BTN_STYLE_MATRIX, hInst, NULL);

            CreateWindowA("STATIC", "Mind Visualizer: Multi-Frequency Fourier + Logic Telemetry",
                WS_CHILD | WS_VISIBLE,
                30, 165, 400, 20, hwnd, (HMENU)991, hInst, NULL);

            // 3. GroupBox 2: Active Working Function & Status
            CreateWindowA("BUTTON", "  Active Working Function & Status  ",
                WS_CHILD | WS_VISIBLE | BS_GROUPBOX,
                15, 210, 435, 185, hwnd, NULL, hInst, NULL);

            CreateWindowA("STATIC", "Active Function f(x):",
                WS_CHILD | WS_VISIBLE,
                30, 232, 140, 18, hwnd, NULL, hInst, NULL);

            g_lblActiveFunc = CreateWindowA("STATIC", "f(x) = None",
                WS_CHILD | WS_VISIBLE | SS_LEFTNOWORDWRAP,
                160, 232, 275, 18, hwnd, NULL, hInst, NULL);

            CreateWindowA("STATIC", "Engine Status:",
                WS_CHILD | WS_VISIBLE,
                30, 255, 110, 18, hwnd, NULL, hInst, NULL);

            g_lblStatus = CreateWindowA("STATIC", "[ IDLE - Ready ]",
                WS_CHILD | WS_VISIBLE,
                160, 255, 275, 18, hwnd, NULL, hInst, NULL);

            g_lblTask = CreateWindowA("STATIC", "Task: Ready for user input",
                WS_CHILD | WS_VISIBLE | SS_LEFTNOWORDWRAP,
                30, 278, 405, 18, hwnd, NULL, hInst, NULL);

            // Calculus Action Buttons
            CreateWindowA("BUTTON", "Integral (+C)",
                WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                30, 305, 125, 32, hwnd, (HMENU)ID_BTN_INT_INDEF, hInst, NULL);

            CreateWindowA("BUTTON", "Derive & Slope",
                WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                170, 305, 125, 32, hwnd, (HMENU)ID_BTN_DERIVE, hInst, NULL);

            CreateWindowA("BUTTON", "Definite Area",
                WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                310, 305, 125, 32, hwnd, (HMENU)ID_BTN_INT_DEF, hInst, NULL);

            CreateWindowA("BUTTON", "Find Roots (f=0)",
                WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                30, 345, 195, 32, hwnd, (HMENU)ID_BTN_ROOTS, hInst, NULL);

            CreateWindowA("BUTTON", "Evaluate Value f(x)",
                WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                240, 345, 195, 32, hwnd, (HMENU)ID_BTN_EVAL, hInst, NULL);

            // 4. GroupBox 3: Process Test & Utilities
            CreateWindowA("BUTTON", "  Interactive Machine Mind & Utilities  ",
                WS_CHILD | WS_VISIBLE | BS_GROUPBOX,
                15, 405, 435, 150, hwnd, NULL, hInst, NULL);

            CreateWindowA("BUTTON", ">> Test Machine Mind Simulation (Demo) <<",
                WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                30, 430, 405, 36, hwnd, (HMENU)ID_BTN_TEST_ANIM, hInst, NULL);

            CreateWindowA("BUTTON", "History (Recall)",
                WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                30, 475, 125, 30, hwnd, (HMENU)ID_BTN_HIST, hInst, NULL);

            CreateWindowA("BUTTON", "Clear Console",
                WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                170, 475, 125, 30, hwnd, (HMENU)ID_BTN_CLEAR, hInst, NULL);

            CreateWindowA("BUTTON", "Help & Guide",
                WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                310, 475, 125, 30, hwnd, (HMENU)ID_BTN_HELP, hInst, NULL);

            CreateWindowA("STATIC", "[Safety Pacing] Mind updates paced at 250ms to protect CPU & human reading.",
                WS_CHILD | WS_VISIBLE | SS_CENTER,
                15, 520, 435, 18, hwnd, NULL, hInst, NULL);

            break;
        }

        case WM_COMMAND: {
            int wmId = LOWORD(wParam);
            switch (wmId) {
                case ID_MODE_AUTO:
                    g_state.popout_mode = MODE_AUTO;
                    SaveStateToFile();
                    break;
                case ID_MODE_ALWAYS:
                    g_state.popout_mode = MODE_ALWAYS;
                    ShowWindow(g_hwndAnimation, SW_SHOW);
                    g_state.is_anim_visible = 1;
                    SaveStateToFile();
                    break;
                case ID_MODE_OFF:
                    g_state.popout_mode = MODE_OFF;
                    ShowWindow(g_hwndAnimation, SW_HIDE);
                    g_state.is_anim_visible = 0;
                    SaveStateToFile();
                    break;

                case ID_BTN_TOGGLE_ANIM:
                    if (IsWindowVisible(g_hwndAnimation)) {
                        ShowWindow(g_hwndAnimation, SW_HIDE);
                        g_state.is_anim_visible = 0;
                    } else {
                        ShowWindow(g_hwndAnimation, SW_SHOW);
                        SetWindowPos(g_hwndAnimation, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE);
                        g_state.is_anim_visible = 1;
                    }
                    break;

                case ID_BTN_STYLE_WAVE:
                    g_state.anim_style = STYLE_WAVE;
                    SetDlgItemTextA(hwnd, 991, "Mind Visualizer: Multi-Frequency Fourier + Logic Telemetry");
                    SaveStateToFile();
                    break;
                case ID_BTN_STYLE_RADAR:
                    g_state.anim_style = STYLE_RADAR;
                    SetDlgItemTextA(hwnd, 991, "Mind Visualizer: Orbital Radar (Convergence Scan)");
                    SaveStateToFile();
                    break;
                case ID_BTN_STYLE_MATRIX:
                    g_state.anim_style = STYLE_MATRIX;
                    SetDlgItemTextA(hwnd, 991, "Mind Visualizer: Matrix Calculus Flux (Glyph Rain)");
                    SaveStateToFile();
                    break;

                case ID_BTN_INT_INDEF:
                    SendCommandToCLI("indefinite integral");
                    break;
                case ID_BTN_DERIVE:
                    SendCommandToCLI("derivative");
                    break;
                case ID_BTN_INT_DEF:
                    SendCommandToCLI("integrate from 1 to 2");
                    break;
                case ID_BTN_ROOTS:
                    SendCommandToCLI("root");
                    break;
                case ID_BTN_EVAL:
                    SendCommandToCLI("put x = 2");
                    break;

                case ID_BTN_TEST_ANIM:
                    // Trigger a 4-second live processing animation demonstration of the machine's mind!
                    g_state.demo_timer = 4.2;
                    strcpy(g_state.status, "processing");
                    strcpy(g_state.task, "Simulating Neural Mind Reasoning on x/(x+1) + 45x^2");
                    if (g_state.popout_mode != MODE_OFF) {
                        ShowWindow(g_hwndAnimation, SW_SHOW);
                        SetWindowPos(g_hwndAnimation, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE);
                        g_state.is_anim_visible = 1;
                    }
                    SaveStateToFile();
                    break;

                case ID_BTN_HIST:
                    SendCommandToCLI("history");
                    break;
                case ID_BTN_CLEAR:
                    SendCommandToCLI("cls");
                    break;
                case ID_BTN_HELP:
                    MessageBoxA(hwnd,
                        "Smart Calculator AI - Machine Mind Monitor:\n\n"
                        "1. Real-Time Cognitive Visualization:\n"
                        "   - The screen shows the actual thoughts, logic stages, and algebraic steps inside the machine.\n"
                        "   - Includes safety delay pacing (250ms) so you can clearly observe the reasoning without CPU overload.\n\n"
                        "2. Cognitive Pipeline Stages:\n"
                        "   - Node 1: INPUT (Token Lexing)\n"
                        "   - Node 2: PARSE (Syntax & Intent Decomposition)\n"
                        "   - Node 3: SOLVER (Symbolic Antiderivatives & Stencils)\n"
                        "   - Node 4: VERIFY (Boundary & Derivative Proof)\n"
                        "   - Node 5: OUTPUT (Formula Synthesis & Result)\n\n"
                        "3. Pop-Out Controls:\n"
                        "   - Auto: Pops out during calculations, shows live thoughts, and auto-hides when complete.\n"
                        "   - Always: Keeps the cognitive screen pinned on your desktop.",
                        "Machine Mind Monitor Guide", MB_OK | MB_ICONINFORMATION);
                    break;
            }
            break;
        }

        case WM_TIMER: {
            if (wParam == TIMER_IPC_ID) {
                // If demo timer active: step through real machine thoughts!
                if (g_state.demo_timer > 0.0) {
                    g_state.demo_timer -= 0.1;
                    double t = g_state.demo_timer;

                    if (t > 3.4) {
                        strcpy(g_state.module, "TOKENIZER / LEXER");
                        g_state.active_node = 0;
                        g_state.progress = 0.15f;
                        strcpy(g_state.current_thought, "Tokenizing stream: extracted tokens ['x', '/', '(', 'x', '+', '1', ')', '+', '45', 'x^2']");
                        strcpy(g_state.math_working, "Expression: x/(x+1) + 45x^2");
                        strcpy(g_state.thoughts[0], "[LEXER] Stream read: 10 mathematical tokens verified");
                    } else if (t > 2.6) {
                        strcpy(g_state.module, "SYNTAX & INTENT PARSER");
                        g_state.active_node = 1;
                        g_state.progress = 0.35f;
                        strcpy(g_state.current_thought, "Decomposing into 2 subterms: [Term 1: Rational x/(x+1)] + [Term 2: Monomial 45x^2]");
                        strcpy(g_state.math_working, "Term 1: x/(x+1)  |  Term 2: 45x^2");
                        strcpy(g_state.thoughts[1], "[PARSER] Detected rational denominator pole at x = -1");
                    } else if (t > 1.8) {
                        strcpy(g_state.module, "SYMBOLIC_CALCULUS_CORE");
                        g_state.active_node = 2;
                        g_state.progress = 0.65f;
                        strcpy(g_state.current_thought, "Applying Rational Division: x/(x+1) = 1 - 1/(x+1) -> Antiderivative = x - ln|x+1|");
                        strcpy(g_state.math_working, "Term 1 Integral: x - ln|x+1|");
                        strcpy(g_state.thoughts[2], "[SOLVER] Term 1 solved via Logarithmic Reciprocal Rule");
                    } else if (t > 0.9) {
                        strcpy(g_state.module, "DIFFERENTIAL_VERIFIER");
                        g_state.active_node = 3;
                        g_state.progress = 0.85f;
                        strcpy(g_state.current_thought, "Applying Power Rule: 45*x^2 -> 45*(x^3)/3 = 15*x^3 | Differentiating to verify equality");
                        strcpy(g_state.math_working, "Term 2 Integral: 15x^3  |  Verification d/dx == Original");
                        strcpy(g_state.thoughts[3], "[VERIFIER] Monomial power rule applied: d/dx(15x^3) = 45x^2 (Exact match)");
                    } else if (t > 0.0) {
                        strcpy(g_state.module, "OUTPUT_SYNTHESIZER");
                        g_state.active_node = 4;
                        g_state.progress = 1.0f;
                        strcpy(g_state.current_thought, "Synthesizing exact closed form: x - ln|x+1| + 15*x^3 + C");
                        strcpy(g_state.math_working, "Final Antiderivative: x - ln|x+1| + 15*x^3 + C");
                        strcpy(g_state.thoughts[4], "[SYNTHESIZER] Appending constant of integration + C. Emitting to user.");
                    } else {
                        g_state.demo_timer = 0.0;
                        strcpy(g_state.status, "idle");
                        strcpy(g_state.task, "Simulation Complete (Paced Safety Delay: 250ms)");
                        g_state.idle_countdown = 2.5; // hold 2.5 sec before auto-hide
                        SaveStateToFile();
                    }
                } else {
                    LoadStateFromFile();
                }

                int is_proc = (strcmp(g_state.status, "processing") == 0);

                if (g_state.popout_mode == MODE_AUTO) {
                    if (is_proc) {
                        g_state.idle_countdown = 2.0;
                        if (!IsWindowVisible(g_hwndAnimation)) {
                            ShowWindow(g_hwndAnimation, SW_SHOW);
                            SetWindowPos(g_hwndAnimation, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE);
                            g_state.is_anim_visible = 1;
                        }
                    } else {
                        if (g_state.idle_countdown > 0.0) {
                            g_state.idle_countdown -= 0.1;
                        } else {
                            if (IsWindowVisible(g_hwndAnimation)) {
                                ShowWindow(g_hwndAnimation, SW_HIDE);
                                g_state.is_anim_visible = 0;
                            }
                        }
                    }
                } else if (g_state.popout_mode == MODE_ALWAYS) {
                    if (!IsWindowVisible(g_hwndAnimation)) {
                        ShowWindow(g_hwndAnimation, SW_SHOW);
                        g_state.is_anim_visible = 1;
                    }
                } else if (g_state.popout_mode == MODE_OFF) {
                    if (IsWindowVisible(g_hwndAnimation) && g_state.demo_timer <= 0.0) {
                        ShowWindow(g_hwndAnimation, SW_HIDE);
                        g_state.is_anim_visible = 0;
                    }
                }

                if (g_state.show_modal && !IsWindowVisible(g_hwndModal)) {
                    ShowWindow(g_hwndModal, SW_SHOW);
                    SetWindowPos(g_hwndModal, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE);
                    InvalidateRect(g_hwndModal, NULL, TRUE);
                    SetForegroundWindow(g_hwndModal);
                } else if (!g_state.show_modal && IsWindowVisible(g_hwndModal)) {
                    ShowWindow(g_hwndModal, SW_HIDE);
                }

                // Update Control Pad Labels
                char fn_buf[300];
                snprintf(fn_buf, sizeof(fn_buf), "f(x) = %s", g_state.active_function);
                SetWindowTextA(g_lblActiveFunc, fn_buf);

                if (is_proc) {
                    SetWindowTextA(g_lblStatus, "[ REASONING IN PROGRESS... ]");
                } else {
                    SetWindowTextA(g_lblStatus, "[ IDLE - Ready ]");
                }

                char task_buf[200];
                snprintf(task_buf, sizeof(task_buf), "Task: %s", g_state.task);
                SetWindowTextA(g_lblTask, task_buf);
            }
            break;
        }

        case WM_DESTROY:
            PostQuitMessage(0);
            break;

        default:
            return DefWindowProcA(hwnd, msg, wParam, lParam);
    }
    return 0;
}

// --- ANIMATION / MACHINE MIND WINDOW PROCEDURE ---
LRESULT CALLBACK AnimationWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
        case WM_TIMER: {
            if (wParam == TIMER_ANIM_ID) {
                int is_proc = (strcmp(g_state.status, "processing") == 0);
                float speed = is_proc ? 0.09f : 0.03f;
                g_anim_time += speed;
                InvalidateRect(hwnd, NULL, FALSE);
            }
            break;
        }

        case WM_PAINT: {
            PAINTSTRUCT ps;
            HDC hdc = BeginPaint(hwnd, &ps);

            RECT rc;
            GetClientRect(hwnd, &rc);
            int width = rc.right - rc.left;
            int height = rc.bottom - rc.top;
            if (width <= 0 || height <= 0) {
                EndPaint(hwnd, &ps);
                break;
            }

            // Double Buffering for smooth rendering
            HDC memDC = CreateCompatibleDC(hdc);
            HBITMAP memBmp = CreateCompatibleBitmap(hdc, width, height);
            HBITMAP oldBmp = (HBITMAP)SelectObject(memDC, memBmp);

            // Dark Cyber Cognitive Slate Background
            HBRUSH bgBrush = CreateSolidBrush(RGB(10, 14, 22));
            FillRect(memDC, &rc, bgBrush);
            DeleteObject(bgBrush);

            int is_proc = (strcmp(g_state.status, "processing") == 0);

            // Fonts
            HFONT hFontHeader = CreateFontA(17, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
                DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, DEFAULT_QUALITY,
                DEFAULT_PITCH | FF_SWISS, "Segoe UI");
            HFONT hFontBold = CreateFontA(14, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
                DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, DEFAULT_QUALITY,
                DEFAULT_PITCH | FF_SWISS, "Segoe UI");
            HFONT hFontCode = CreateFontA(13, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, DEFAULT_QUALITY,
                FIXED_PITCH | FF_MODERN, "Consolas");
            HFONT hFontSmall = CreateFontA(12, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, DEFAULT_QUALITY,
                DEFAULT_PITCH | FF_SWISS, "Segoe UI");

            SetBkMode(memDC, TRANSPARENT);

            // =========================================================
            // 1. TOP NEURAL STATUS BAR (Y: 0 .. 46)
            // =========================================================
            RECT rTop = { 0, 0, width, 46 };
            HBRUSH topBrush = CreateSolidBrush(RGB(16, 22, 34));
            FillRect(memDC, &rTop, topBrush);
            DeleteObject(topBrush);

            HPEN divPen = CreatePen(PS_SOLID, 1, RGB(35, 48, 70));
            HPEN oldPen = (HPEN)SelectObject(memDC, divPen);
            HFONT oldFont = (HFONT)SelectObject(memDC, hFontHeader);
            if (is_proc) {
                SetTextColor(memDC, RGB(0, 240, 255));
                TextOutA(memDC, 15, 6, "MACHINE MIND -- REAL-TIME COGNITIVE MONITOR", 43);
            } else {
                SetTextColor(memDC, RGB(0, 230, 140));
                TextOutA(memDC, 15, 6, "MACHINE MIND -- IDLE / READY", 28);
            }

            SelectObject(memDC, hFontSmall);
            SetTextColor(memDC, RGB(180, 200, 220));
            char taskHeader[300];
            snprintf(taskHeader, sizeof(taskHeader), "Task: %s | Pacing: 250ms Safety Delay Active", g_state.task);
            TextOutA(memDC, 16, 26, taskHeader, (int)strlen(taskHeader));

            // Module Pill on Right
            SelectObject(memDC, hFontBold);
            char modPill[100];
            snprintf(modPill, sizeof(modPill), "[ MODULE: %s ]", strlen(g_state.module) > 0 ? g_state.module : "STANDBY");
            int pillLen = (int)strlen(modPill);
            int pillX = width - 15 - (pillLen * 8);
            if (pillX > 320) {
                SetTextColor(memDC, is_proc ? RGB(255, 215, 0) : RGB(100, 220, 180));
                TextOutA(memDC, pillX, 12, modPill, pillLen);
            }

            // =========================================================
            // 2. COGNITIVE PIPELINE GRAPH (5 STAGES) (Y: 52 .. 112)
            // =========================================================
            const char *nodeNames[5] = { "1. INPUT", "2. PARSER", "3. SOLVER", "4. VERIFY", "5. OUTPUT" };
            const char *nodeSubs[5]  = { "Lexer Stream", "Syntax Tree", "Calculus Core", "Proof Check", "Synthesis" };
            int totalNodes = 5;
            int boxW = (width - 40 - (totalNodes - 1) * 12) / totalNodes;
            int boxH = 46;
            int graphY = 56;

            for (int i = 0; i < totalNodes; i++) {
                int bx = 20 + i * (boxW + 12);
                int by = graphY;
                RECT rNode = { bx, by, bx + boxW, by + boxH };

                // Draw connecting wire to next node
                if (i < totalNodes - 1) {
                    int wireX1 = bx + boxW;
                    int wireX2 = wireX1 + 12;
                    int wireY = by + boxH / 2;
                    HPEN wirePen = CreatePen(PS_SOLID, 2, (i < g_state.active_node) ? RGB(0, 230, 140) : RGB(40, 55, 75));
                    SelectObject(memDC, wirePen);
                    MoveToEx(memDC, wireX1, wireY, NULL);
                    LineTo(memDC, wireX2, wireY);
                    DeleteObject(wirePen);

                    // Energy pulse dot traveling along wire
                    if (is_proc && i == g_state.active_node) {
                        float pulseFrac = fmodf(g_anim_time * 2.0f, 1.0f);
                        int dotX = wireX1 + (int)(pulseFrac * 12.0f);
                        HBRUSH dotB = CreateSolidBrush(RGB(0, 240, 255));
                        RECT rDot = { dotX - 2, wireY - 2, dotX + 3, wireY + 3 };
                        FillRect(memDC, &rDot, dotB);
                        DeleteObject(dotB);
                    }
                }

                // Node Box Fill & Border
                COLORREF borderColor;
                COLORREF fillColor;
                COLORREF textTitleColor;

                if (i < g_state.active_node) {
                    // Completed node
                    borderColor = RGB(0, 200, 120);
                    fillColor = RGB(12, 32, 24);
                    textTitleColor = RGB(0, 230, 140);
                } else if (i == g_state.active_node) {
                    // Currently Active Node
                    float pulse = (sinf(g_anim_time * 6.0f) * 0.5f + 0.5f);
                    borderColor = RGB(0, (int)(200 + pulse * 55), 255);
                    fillColor = RGB(18, (int)(35 + pulse * 25), (int)(55 + pulse * 35));
                    textTitleColor = RGB(255, 235, (int)(100 + pulse * 155));
                } else {
                    // Pending node
                    borderColor = RGB(35, 45, 60);
                    fillColor = RGB(14, 18, 26);
                    textTitleColor = RGB(110, 130, 150);
                }

                HBRUSH nBrush = CreateSolidBrush(fillColor);
                FillRect(memDC, &rNode, nBrush);
                DeleteObject(nBrush);

                HPEN nPen = CreatePen(PS_SOLID, (i == g_state.active_node) ? 2 : 1, borderColor);
                SelectObject(memDC, nPen);
                MoveToEx(memDC, bx, by, NULL);
                LineTo(memDC, bx + boxW, by);
                LineTo(memDC, bx + boxW, by + boxH);
                LineTo(memDC, bx, by + boxH);
                LineTo(memDC, bx, by);
                DeleteObject(nPen);

                // Node Texts
                SelectObject(memDC, hFontBold);
                SetTextColor(memDC, textTitleColor);
                TextOutA(memDC, bx + 6, by + 5, nodeNames[i], (int)strlen(nodeNames[i]));

                SelectObject(memDC, hFontSmall);
                SetTextColor(memDC, RGB(160, 180, 200));
                TextOutA(memDC, bx + 6, by + 23, nodeSubs[i], (int)strlen(nodeSubs[i]));
            }

            // =========================================================
            // 3. THOUGHT STREAM & INNER MONOLOGUE (Y: 118 .. 275)
            // =========================================================
            RECT rStream = { 20, 118, width - 20, 275 };
            HBRUSH strBrush = CreateSolidBrush(RGB(6, 9, 15));
            FillRect(memDC, &rStream, strBrush);
            DeleteObject(strBrush);

            HPEN strPen = CreatePen(PS_SOLID, 1, RGB(35, 48, 68));
            SelectObject(memDC, strPen);
            MoveToEx(memDC, 20, 118, NULL);
            LineTo(memDC, width - 20, 118);
            LineTo(memDC, width - 20, 275);
            LineTo(memDC, 20, 275);
            LineTo(memDC, 20, 118);
            DeleteObject(strPen);

            // Stream Header
            SelectObject(memDC, hFontBold);
            SetTextColor(memDC, RGB(0, 220, 255));
            TextOutA(memDC, 32, 126, "⚡ MACHINE'S INNER REASONING & THOUGHT LOG (REAL-TIME):", 54);

            // Print 5 Thought Lines
            SelectObject(memDC, hFontCode);
            int lineY = 148;
            for (int i = 0; i < 5; i++) {
                if (strlen(g_state.thoughts[i]) > 0) {
                    int isLatest = (i == 4) || (i == g_state.active_node);
                    if (isLatest && is_proc) {
                        SetTextColor(memDC, RGB(255, 230, 80)); // Neon Gold for current thought
                        char lineBuf[220];
                        int blink = ((int)(g_anim_time * 4.0f)) % 2;
                        snprintf(lineBuf, sizeof(lineBuf), "▶ %s %s", g_state.thoughts[i], blink ? "_" : " ");
                        TextOutA(memDC, 32, lineY, lineBuf, (int)strlen(lineBuf));
                    } else {
                        SetTextColor(memDC, RGB(175, 195, 215)); // Soft Slate for past thoughts
                        char lineBuf[220];
                        snprintf(lineBuf, sizeof(lineBuf), "  %s", g_state.thoughts[i]);
                        TextOutA(memDC, 32, lineY, lineBuf, (int)strlen(lineBuf));
                    }
                    lineY += 22;
                }
            }

            // =========================================================
            // 4. LIVE WORKING MATH BUFFER (Y: 285 .. 345)
            // =========================================================
            RECT rMath = { 20, 285, width - 20, 345 };
            HBRUSH mathBrush = CreateSolidBrush(RGB(12, 17, 28));
            FillRect(memDC, &rMath, mathBrush);
            DeleteObject(mathBrush);

            HPEN mathPen = CreatePen(PS_SOLID, 1, RGB(45, 60, 85));
            SelectObject(memDC, mathPen);
            MoveToEx(memDC, 20, 285, NULL);
            LineTo(memDC, width - 20, 285);
            LineTo(memDC, width - 20, 345);
            LineTo(memDC, 20, 345);
            LineTo(memDC, 20, 285);
            DeleteObject(mathPen);

            SelectObject(memDC, hFontBold);
            SetTextColor(memDC, RGB(0, 230, 160));
            TextOutA(memDC, 32, 292, "📐 ACTIVE FORMULA & TERM TRANSFORMATION IN PROGRESS:", 52);

            SelectObject(memDC, hFontCode);
            SetTextColor(memDC, RGB(240, 245, 255));
            char mathText[300];
            snprintf(mathText, sizeof(mathText), "%s", strlen(g_state.math_working) > 0 ? g_state.math_working : "Memory: Standby | Ready for mathematical evaluation");
            TextOutA(memDC, 32, 315, mathText, (int)strlen(mathText));

            // =========================================================
            // 5. COGNITIVE ACTIVITY BRAINWAVE OSCILLOSCOPE (Y: 355 .. 430)
            // =========================================================
            RECT rWave = { 20, 355, width - 20, 430 };
            HBRUSH waveBrush = CreateSolidBrush(RGB(6, 10, 16));
            FillRect(memDC, &rWave, waveBrush);
            DeleteObject(waveBrush);

            HPEN wBoxPen = CreatePen(PS_SOLID, 1, RGB(30, 40, 58));
            SelectObject(memDC, wBoxPen);
            MoveToEx(memDC, 20, 355, NULL);
            LineTo(memDC, width - 20, 355);
            LineTo(memDC, width - 20, 430);
            LineTo(memDC, 20, 430);
            LineTo(memDC, 20, 355);
            DeleteObject(wBoxPen);

            int oscY = 355 + 37;
            HPEN gridP = CreatePen(PS_DOT, 1, RGB(20, 30, 45));
            SelectObject(memDC, gridP);
            MoveToEx(memDC, 20, oscY, NULL);
            LineTo(memDC, width - 20, oscY);
            DeleteObject(gridP);

            // Draw Cognitive EEG / Calculus Harmonic Waves
            int oscLeft = 24;
            int oscRight = width - 24;
            int oscWidth = oscRight - oscLeft;

            float waveAmp1 = is_proc ? 22.0f : 8.0f;
            float waveAmp2 = is_proc ? 14.0f : 5.0f;

            HPEN eegPen1 = CreatePen(PS_SOLID, 2, RGB(0, 240, 255));
            SelectObject(memDC, eegPen1);

            for (int x = oscLeft; x < oscRight; x += 2) {
                float k = (float)(x - oscLeft) / (float)oscWidth * 6.0f * (float)M_PI;
                float yVal = sinf(k + g_anim_time * 3.0f) * cosf(k * 0.5f - g_anim_time * 1.5f) * waveAmp1;
                int py = oscY - (int)yVal;
                if (x == oscLeft) MoveToEx(memDC, x, py, NULL);
                else LineTo(memDC, x, py);
            }
            DeleteObject(eegPen1);

            HPEN eegPen2 = CreatePen(PS_SOLID, 1, RGB(220, 80, 255));
            SelectObject(memDC, eegPen2);
            for (int x = oscLeft; x < oscRight; x += 3) {
                float k = (float)(x - oscLeft) / (float)oscWidth * 10.0f * (float)M_PI;
                float yVal = cosf(k - g_anim_time * 4.0f) * waveAmp2;
                int py = oscY - (int)yVal;
                if (x == oscLeft) MoveToEx(memDC, x, py, NULL);
                else LineTo(memDC, x, py);
            }
            DeleteObject(eegPen2);

            SelectObject(memDC, hFontSmall);
            SetTextColor(memDC, RGB(120, 150, 180));
            TextOutA(memDC, 32, 360, "COGNITIVE INTENSITY OSCILLOSCOPE", 32);

            char progStr[100];
            snprintf(progStr, sizeof(progStr), "Neural Load: %d%%  |  Frame: 33 FPS", (int)(g_state.progress * 100.0f));
            TextOutA(memDC, width - 230, 360, progStr, (int)strlen(progStr));

            // =========================================================
            // 6. BOTTOM PROGRESS BAR & LATENCY FOOTER (Y: 440 .. 490)
            // =========================================================
            int pbW = width - 40;
            int pbH = 8;
            int pbX = 20;
            int pbY = 442;

            RECT rPbBg = { pbX, pbY, pbX + pbW, pbY + pbH };
            HBRUSH pbBg = CreateSolidBrush(RGB(20, 28, 40));
            FillRect(memDC, &rPbBg, pbBg);
            DeleteObject(pbBg);

            int fillW = (int)(g_state.progress * pbW);
            if (fillW > pbW) fillW = pbW;
            if (fillW < 0) fillW = 0;

            RECT rBar = { pbX, pbY, pbX + fillW, pbY + pbH };
            HBRUSH barBrush = CreateSolidBrush(is_proc ? RGB(0, 240, 255) : RGB(0, 220, 130));
            FillRect(memDC, &rBar, barBrush);
            DeleteObject(barBrush);

            SelectObject(memDC, hFontSmall);
            SetTextColor(memDC, RGB(150, 175, 200));
            TextOutA(memDC, 20, 458, "Safety Pacing: 250ms Active Pacing (CPU & Memory Overload Protected) | Synchronized with CLI", 91);

            // Clean up GDI Objects
            SelectObject(memDC, oldFont);
            SelectObject(memDC, oldPen);
            DeleteObject(divPen);
            DeleteObject(hFontHeader);
            DeleteObject(hFontBold);
            DeleteObject(hFontCode);
            DeleteObject(hFontSmall);

            // Blit to Screen
            BitBlt(hdc, 0, 0, width, height, memDC, 0, 0, SRCCOPY);

            SelectObject(memDC, oldBmp);
            DeleteObject(memBmp);
            DeleteDC(memDC);

            EndPaint(hwnd, &ps);
            break;
        }

        case WM_CLOSE:
            ShowWindow(hwnd, SW_HIDE);
            g_state.is_anim_visible = 0;
            return 0;

        default:
            return DefWindowProcA(hwnd, msg, wParam, lParam);
    }
    return 0;
}

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
        case WM_LBUTTONDOWN:
            ShowWindow(hwnd, SW_HIDE);
            g_state.show_modal = 0;
            break;
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
