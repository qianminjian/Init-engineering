@echo off
REM Maven Wrapper startup batch script for Windows
REM ----------------------------------------------------------------------------

setlocal enabledelayedexpansion

set "MAVEN_PROJECTBASEDIR=%~dp0"
set "WRAPPER_JAR=%MAVEN_PROJECTBASEDIR%.mvn\wrapper\maven-wrapper.jar"
set "WRAPPER_PROPERTIES=%MAVEN_PROJECTBASEDIR%.mvn\wrapper\maven-wrapper.properties"

if not defined MAVEN_HOME set "MAVEN_HOME=%MAVEN_PROJECTBASEDIR%.mvn\wrapper\maven-home"

if not defined JAVA_HOME (
  echo ERROR: JAVA_HOME is not set. Please set JAVA_HOME to a JDK installation.
  exit /b 1
)

set "JAVA_EXEC=%JAVA_HOME%\bin\java.exe"
set MAVEN_OPTS=%MAVEN_OPTS% -Xmx1024m -XX:MaxMetaspaceSize=256m

if not exist "%WRAPPER_JAR%" (
  echo Downloading Maven Wrapper...
  for /f "tokens=2 delims==" %%a in ('findstr "wrapperUrl=" "%WRAPPER_PROPERTIES%"') do set "WRAPPER_URL=%%a"
  powershell -Command "Invoke-WebRequest -Uri '%WRAPPER_URL%' -OutFile '%WRAPPER_JAR%'"
)

"%JAVA_EXEC%" ^
  %MAVEN_OPTS% ^
  -classpath "%WRAPPER_JAR%" ^
  "-Dmaven.multiModuleProjectDirectory=%MAVEN_PROJECTBASEDIR%" ^
  %WRAPPER_LAUNCHER% org.apache.maven.wrapper.MavenWrapperMain ^
  %*
