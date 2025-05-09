const path = require('path');
const childProcess = require('child_process');
const fs = require('fs');

function getPythonExecutable() {
  // Default to 'python3', which should be available in most GitHub runners
  return process.env.PYTHON_EXECUTABLE || 'python3';
}

function getMainPythonScript() {
  // Path to your main Python script
  return path.join(__dirname, 'src', 'main.py');
}

// Ensure the Python script is executable
function ensureExecutable(scriptPath) {
  try {
    fs.chmodSync(scriptPath, '755');
  } catch (error) {
    console.error(`Failed to make script executable: ${error.message}`);
  }
}

// Install Python dependencies from requirements.txt if present
function installDependencies() {
  const requirementsPath = path.join(__dirname, 'requirements.txt');
  
  if (fs.existsSync(requirementsPath)) {
    console.log('Installing Python dependencies...');
    const installResult = childProcess.spawnSync(
      getPythonExecutable(),
      ['-m', 'pip', 'install', '-r', requirementsPath],
      { stdio: 'inherit' }
    );
    
    if (installResult.status !== 0) {
      console.error('Failed to install dependencies');
      process.exit(installResult.status);
    }
  } else {
    console.log('No requirements.txt found, skipping dependency installation');
  }
}

// Main execution logic
function runPythonScript() {
  const pythonExecutable = getPythonExecutable();
  const mainScript = getMainPythonScript();
  
  // Make sure the script is executable
  ensureExecutable(mainScript);
  
  // Get arguments to pass to the Python script
  const args = process.argv.slice(2);
  
  console.log(`Executing: ${pythonExecutable} ${mainScript} ${args.join(' ')}`);
  
  // Run the Python script with the same arguments passed to this script
  const spawnSyncReturns = childProcess.spawnSync(
    pythonExecutable, 
    [mainScript, ...args], 
    { 
      stdio: 'inherit',
      env: process.env
    }
  );
  
  // Forward the exit code from the Python script
  process.exit(spawnSyncReturns.status);
}

// Execute the workflow: install dependencies first, then run the script
function main() {
  try {
    // First install any required dependencies
    installDependencies();
    
    // Then run the main Python script
    runPythonScript();
  } catch (error) {
    console.error(`Error executing Python script: ${error.message}`);
    process.exit(1);
  }
}

// Run the main function
main();