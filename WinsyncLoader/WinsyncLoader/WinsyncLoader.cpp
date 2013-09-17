// WinsyncLoader.cpp : Defines the entry point for the application.
//

#include "stdafx.h"
#include "WinsyncLoader.h"
#include <strsafe.h>
#include <stdio.h>

#define MAX_LOADSTRING 100

//Retrieves the last windows error. It then shows a mesagebox with
//a nicely formated message containing the windows error message
//for the GetLastError() number. The parameter should be the
//name of the function generating the error.
void error_exit(_In_ LPTSTR lpszFunction);

void error_code_exit(_In_ LPTSTR lpszFunction, _In_ DWORD error_code);

//Displays the given message in an error message box, it then exit's the process.
void msg_exit(_In_ LPTSTR msg);

//Finds the Winsync installation and sends back the path to the
//Python installation directory that has Winsync installed.
void find_winsync(_Out_ LPTSTR path);

int APIENTRY _tWinMain(HINSTANCE hInstance,
                       HINSTANCE hPrevInstance,
                       LPTSTR    lpCmdLine,
                       int       nCmdShow)
{
	UNREFERENCED_PARAMETER(hPrevInstance);
	UNREFERENCED_PARAMETER(lpCmdLine);

    TCHAR path[MAX_PATH];
    TCHAR appname[MAX_PATH];

	STARTUPINFO info;
	PROCESS_INFORMATION processInfo;

    //Find the winsync install
	find_winsync(path);
    
    //Calculate the location for python.exe
    _tcscpy_s(appname, MAX_PATH, path);
    _tcscat_s(appname, MAX_PATH, _T("python.exe"));

    //Create the command line
    _tcscat_s(appname, MAX_PATH, _T(" -m winsync.run"));

    //Make the console window shows up
    SecureZeroMemory(&info, sizeof(info));
    info.cb = sizeof(info);
    info.dwFlags = STARTF_USESHOWWINDOW;
    info.wShowWindow = SW_SHOW;

	//Start the python process
	if (!CreateProcess(NULL, appname, NULL, NULL, TRUE,
					   CREATE_NEW_CONSOLE | CREATE_PRESERVE_CODE_AUTHZ_LEVEL,
				 	   NULL, path, &info, &processInfo))
		error_exit(_T("CreateProcess"));

	//Wait for the python process to end,
    //also handle the various error conditions
	switch(WaitForSingleObject(processInfo.hProcess, INFINITE)) {
		case WAIT_ABANDONED: msg_exit(_T("Wait abandoned"));
		case WAIT_TIMEOUT: msg_exit(_T("Timout reached, should have waited indefinately."));
		case WAIT_FAILED: error_exit(_T("WaitForSingleObject"));
	}

	//Close the process & thread handles
	if (!CloseHandle(processInfo.hProcess))
		error_exit(_T("CloseHandle (process)"));
	if (!CloseHandle(processInfo.hThread))
		error_exit(_T("CloseHandle (thread)"));
}

void find_winsync(LPTSTR path) {
	HKEY root;
	DWORD ret;
	DWORD index = 0;
	TCHAR name[MAX_PATH];
    TCHAR keyname[MAX_PATH];
    TCHAR paths[MAX_PATH];
    TCHAR *tok_context;
	DWORD name_size = MAX_PATH;
    DWORD path_size = MAX_PATH;

    TCHAR *token;

	LPTSTR keys[2] = { _T("SOFTWARE\\Python\\PythonCore"),
					   _T("SOFTWARE\\Wow6432Node\\Python\\PythonCore") };
	
	//Try finding the list of installed python's in the registry
	ret = RegOpenKeyEx(HKEY_LOCAL_MACHINE, keys[0], 0,
			 		  KEY_READ | KEY_ENUMERATE_SUB_KEYS, &root);
		
	//Failed to find the key.
	//Try looking in the WOW64 registry
	if (ret != ERROR_SUCCESS)
		ret = RegOpenKeyEx(HKEY_LOCAL_MACHINE, keys[1], 0,
						   KEY_READ | KEY_ENUMERATE_SUB_KEYS, &root);
		if ( ret != ERROR_SUCCESS)
			error_code_exit(_T("RegOpenKeyEx"), ret);

	//Enumerate all of the python installs
    ret = RegEnumKeyEx(root, index++, keyname, &name_size, NULL, NULL, NULL, NULL);
	while (ERROR_SUCCESS == ret) {
		//We need to look in the PythonPath subkey
        _tcscpy_s(name, MAX_PATH, keyname);
		_tcscat_s(name, MAX_PATH, _T("\\PythonPath"));
        
        //Get the default value for the path key
        ret = RegGetValue(root, name, NULL, RRF_RT_REG_SZ, NULL, paths, &path_size);

        //Sometimes uninstallers leave bad entries. There is no
        //PythonPath for this entry, so skip it.
        if (ret == ERROR_SUCCESS) {
            
            //The paths are a is a semi-colon delimited list of paths
            token = _tcstok_s(paths, _T(";"), &tok_context);
            while (token != NULL) {
                _tcscpy_s(path, MAX_PATH, token);
                _tcscat_s(path, MAX_PATH, _T("\\site-packages\\winsync"));

                //If winsync is install on this path, get the install path
                ret = GetFileAttributes(path);
                if (ret != INVALID_FILE_ATTRIBUTES) {
                    //Calculate the InstallPath key name
                    _tcscpy_s(name, MAX_PATH, keyname);
		            _tcscat_s(name, MAX_PATH, _T("\\InstallPath"));

                    //Get the InstallPath's value into the out parameter
                    ret = RegGetValue(root, name, NULL, RRF_RT_REG_SZ, NULL,
                                      path, &path_size);
                    if (ret != ERROR_SUCCESS)
                        error_code_exit(_T("RegGetValue (installpath)"), ret);
                    
                    return;
                }
                        

                //Get next path
                token = _tcstok_s(NULL, _T(";"), &tok_context);
            }
        } else if (ret != 2) {
            error_code_exit(_T("RegGetValue"), ret);
        }

        //Reset the size parameter
        name_size = MAX_PATH;
        ret = RegEnumKeyEx(root, index++, keyname, &name_size, NULL, NULL, NULL, NULL);
	}

    //If we got here, then winsync was never found
    if (ret == ERROR_NO_MORE_ITEMS)
        msg_exit(_T("Could not find a WinSync install"));
    else
        error_code_exit(_T("RegEnumKeyEx"), ret);
}

BOOL is_64_bit_windows()
{
#if defined(_WIN64)
    return TRUE;  // 64-bit programs run only on Win64
#elif defined(_WIN32)
    // 32-bit programs run on both 32-bit and 64-bit Windows
    // so must sniff
    BOOL f64 = FALSE;
    return IsWow64Process(GetCurrentProcess(), &f64) && f64;
#else
    return FALSE; // Win64 does not support Win16
#endif
}

void error_exit(LPTSTR lpszFunction)
{
	error_code_exit(lpszFunction, GetLastError());
}

void error_code_exit(LPTSTR lpszFunction, DWORD error_code)
{ 
    // Retrieve the system error message for the last-error code

    LPVOID lpMsgBuf;
    LPVOID lpDisplayBuf;

    FormatMessage(
        FORMAT_MESSAGE_ALLOCATE_BUFFER | 
        FORMAT_MESSAGE_FROM_SYSTEM |
        FORMAT_MESSAGE_IGNORE_INSERTS,
        NULL,
        error_code,
        MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        (LPTSTR) &lpMsgBuf,
        0, NULL );

    // Display the error message and exit the process
    lpDisplayBuf = (LPVOID)LocalAlloc(LMEM_ZEROINIT, 
        (lstrlen((LPCTSTR)lpMsgBuf) + lstrlen((LPCTSTR)lpszFunction) + 40) * sizeof(TCHAR)); 
    
	StringCchPrintf((LPTSTR)lpDisplayBuf, 
        LocalSize(lpDisplayBuf) / sizeof(TCHAR),
        TEXT("%s failed with error %d: %s"), 
        lpszFunction, error_code, lpMsgBuf); 
    
	MessageBox(NULL, (LPCTSTR)lpDisplayBuf, TEXT("Error"), MB_ICONERROR | MB_OK); 

    LocalFree(lpMsgBuf);
    LocalFree(lpDisplayBuf);
    ExitProcess(error_code); 
}

void msg_exit(LPTSTR msg) {
	MessageBox(NULL, msg, _T("ERROR"), MB_ICONERROR | MB_OK);
	ExitProcess(255);
}
