#pragma once

// Windows-only compatibility layer for database_cache_harness_main.cpp.
// It maps the three POSIX facilities used by that research harness onto
// Win32 file times, DACLs, and explicit identity sentinels.

#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QHash>
#include <QString>

#include <aclapi.h>
#include <windows.h>

#include <cerrno>
#include <cstdint>
#include <vector>

#pragma comment(lib, "Advapi32.lib")

#ifndef AT_FDCWD
#define AT_FDCWD (-100)
#endif

typedef int mode_t;

namespace diec_windows_cache_compat {

struct SecuritySnapshot {
    PSECURITY_DESCRIPTOR descriptor = nullptr;
    PACL dacl = nullptr;
};

inline QHash<QString, SecuritySnapshot> &securitySnapshots()
{
    static QHash<QString, SecuritySnapshot> snapshots;
    return snapshots;
}

inline QString canonicalSecurityPath(const char *path)
{
    return QDir::toNativeSeparators(
        QFileInfo(QString::fromLocal8Bit(path)).absoluteFilePath()
    );
}

inline bool currentUserSid(std::vector<unsigned char> *storage)
{
    HANDLE token = nullptr;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token)) {
        return false;
    }
    DWORD size = 0;
    GetTokenInformation(token, TokenUser, nullptr, 0, &size);
    if (GetLastError() != ERROR_INSUFFICIENT_BUFFER || size == 0) {
        CloseHandle(token);
        return false;
    }
    storage->resize(size);
    const bool result = GetTokenInformation(
        token,
        TokenUser,
        storage->data(),
        size,
        &size
    ) != FALSE;
    CloseHandle(token);
    return result;
}

inline bool denyAccess(
    const QString &path,
    DWORD permissions,
    DWORD inheritance
)
{
    if (securitySnapshots().contains(path)) {
        return false;
    }

    PACL oldDacl = nullptr;
    PSECURITY_DESCRIPTOR descriptor = nullptr;
    QString mutablePath = path;
    const DWORD readStatus = GetNamedSecurityInfoW(
        reinterpret_cast<LPWSTR>(mutablePath.data()),
        SE_FILE_OBJECT,
        DACL_SECURITY_INFORMATION,
        nullptr,
        nullptr,
        &oldDacl,
        nullptr,
        &descriptor
    );
    if (readStatus != ERROR_SUCCESS) {
        return false;
    }

    std::vector<unsigned char> tokenStorage;
    if (!currentUserSid(&tokenStorage)) {
        LocalFree(descriptor);
        return false;
    }
    const TOKEN_USER *tokenUser = reinterpret_cast<const TOKEN_USER *>(
        tokenStorage.data()
    );

    EXPLICIT_ACCESSW access = {};
    access.grfAccessPermissions = permissions;
    access.grfAccessMode = DENY_ACCESS;
    access.grfInheritance = inheritance;
    access.Trustee.TrusteeForm = TRUSTEE_IS_SID;
    access.Trustee.TrusteeType = TRUSTEE_IS_USER;
    access.Trustee.ptstrName = reinterpret_cast<LPWSTR>(
        tokenUser->User.Sid
    );

    PACL deniedDacl = nullptr;
    const DWORD aclStatus = SetEntriesInAclW(
        1,
        &access,
        oldDacl,
        &deniedDacl
    );
    if (aclStatus != ERROR_SUCCESS) {
        LocalFree(descriptor);
        return false;
    }

    const DWORD writeStatus = SetNamedSecurityInfoW(
        reinterpret_cast<LPWSTR>(mutablePath.data()),
        SE_FILE_OBJECT,
        DACL_SECURITY_INFORMATION,
        nullptr,
        nullptr,
        deniedDacl,
        nullptr
    );
    LocalFree(deniedDacl);
    if (writeStatus != ERROR_SUCCESS) {
        LocalFree(descriptor);
        return false;
    }

    securitySnapshots().insert(
        path,
        SecuritySnapshot{descriptor, oldDacl}
    );
    return true;
}

inline bool restoreAccess(const QString &path)
{
    if (!securitySnapshots().contains(path)) {
        return true;
    }
    const SecuritySnapshot snapshot = securitySnapshots().take(path);
    QString mutablePath = path;
    const DWORD status = SetNamedSecurityInfoW(
        reinterpret_cast<LPWSTR>(mutablePath.data()),
        SE_FILE_OBJECT,
        DACL_SECURITY_INFORMATION,
        nullptr,
        nullptr,
        snapshot.dacl,
        nullptr
    );
    LocalFree(snapshot.descriptor);
    return status == ERROR_SUCCESS;
}

}  // namespace diec_windows_cache_compat

extern "C" inline int utimensat(
    int directory,
    const char *path,
    const struct timespec times[2],
    int flags
)
{
    if (
        directory != AT_FDCWD ||
        path == nullptr ||
        times == nullptr ||
        flags != 0
    ) {
        errno = EINVAL;
        return -1;
    }
    QFile file(QString::fromLocal8Bit(path));
    if (!file.open(QIODevice::ReadWrite)) {
        errno = EACCES;
        return -1;
    }
    const qint64 milliseconds =
        static_cast<qint64>(times[1].tv_sec) * 1000 +
        static_cast<qint64>(times[1].tv_nsec) / 1000000;
    const QDateTime modified = QDateTime::fromMSecsSinceEpoch(
        milliseconds,
        Qt::UTC
    );
    if (!file.setFileTime(modified, QFileDevice::FileModificationTime)) {
        errno = EIO;
        return -1;
    }
    return 0;
}

extern "C" inline int chmod(const char *path, mode_t mode)
{
    if (path == nullptr) {
        errno = EINVAL;
        return -1;
    }
    const QString securityPath =
        diec_windows_cache_compat::canonicalSecurityPath(path);
    bool success = false;
    if (mode == 0555) {
        success = diec_windows_cache_compat::denyAccess(
            securityPath,
            FILE_ADD_FILE |
                FILE_ADD_SUBDIRECTORY |
                FILE_WRITE_DATA |
                FILE_APPEND_DATA |
                FILE_DELETE_CHILD,
            NO_INHERITANCE
        );
    } else if (mode == 0000) {
        const bool isDirectory = QFileInfo(securityPath).isDir();
        const DWORD permissions = isDirectory
            ? (
                GENERIC_READ |
                GENERIC_EXECUTE |
                FILE_LIST_DIRECTORY |
                FILE_TRAVERSE
            )
            : (GENERIC_READ | FILE_READ_DATA);
        success = diec_windows_cache_compat::denyAccess(
            securityPath,
            permissions,
            isDirectory
                ? (SUB_CONTAINERS_AND_OBJECTS_INHERIT)
                : NO_INHERITANCE
        );
    } else {
        success =
            diec_windows_cache_compat::restoreAccess(securityPath);
    }
    if (!success) {
        errno = EACCES;
        return -1;
    }
    return 0;
}

inline qint64 geteuid()
{
    return -1;
}

inline qint64 getegid()
{
    return -1;
}
