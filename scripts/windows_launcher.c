#define UNICODE
#define _UNICODE
#include <windows.h>
#include <wchar.h>
#include <stdio.h>

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR command, int show) {
    (void)inst; (void)prev; (void)command; (void)show;
    wchar_t base[32768], python[32768], script[32768], args[32768];
    DWORD n = GetModuleFileNameW(NULL, base, 32768);
    if (!n || n >= 32000) return 1;
    wchar_t *slash = wcsrchr(base, L'\\');
    if (!slash) return 1;
    *slash = L'\0';
    if (wcslen(base) > 15000) {
        MessageBoxW(NULL, L"解压路径太长，请解压到较短的文件夹路径。", L"媒体 GPS 检查器", MB_ICONERROR);
        return 1;
    }
    swprintf(python, 32768, L"%ls\\_runtime\\pythonw.exe", base);
    swprintf(script, 32768, L"%ls\\portable_start.py", base);
    if (GetFileAttributesW(python) == INVALID_FILE_ATTRIBUTES || GetFileAttributesW(script) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxW(NULL, L"请先完整解压整个文件夹，再双击本程序。不要只复制 exe。", L"媒体 GPS 检查器", MB_ICONERROR);
        return 1;
    }
    swprintf(args, 32768, L"\"%ls\" -B \"%ls\"", python, script);
    STARTUPINFOW si = {0};
    PROCESS_INFORMATION pi = {0};
    si.cb = sizeof(si);
    if (!CreateProcessW(python, args, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, base, &si, &pi)) {
        wchar_t message[1024];
        swprintf(message, 1024, L"启动失败（错误 %lu）。请确认已完整解压，使用 Windows 10/11 64 位。", GetLastError());
        MessageBoxW(NULL, message, L"媒体 GPS 检查器", MB_ICONERROR);
        return 1;
    }
    CloseHandle(pi.hThread);
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD code = 1;
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hProcess);
    if (code != 0) {
        MessageBoxW(NULL, L"程序未能正常运行。请打开同文件夹的“启动诊断.cmd”，将显示的错误发给助手。", L"媒体 GPS 检查器", MB_ICONERROR);
    }
    return (int)code;
}
