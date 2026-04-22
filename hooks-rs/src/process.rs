use std::process::{Command, Output, Stdio};
use std::time::Duration;
use wait_timeout::ChildExt;

pub enum CommandError {
    Io(std::io::Error),
    TimedOut,
}

pub fn output_with_timeout(
    command: &mut Command,
    timeout: Duration,
) -> Result<Output, CommandError> {
    command.stdout(Stdio::piped()).stderr(Stdio::piped());
    let mut child = command.spawn().map_err(CommandError::Io)?;

    match child.wait_timeout(timeout).map_err(CommandError::Io)? {
        Some(_) => child.wait_with_output().map_err(CommandError::Io),
        None => {
            let _ = child.kill();
            let _ = child.wait();
            Err(CommandError::TimedOut)
        }
    }
}

pub fn combined_output(output: &Output) -> String {
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();

    match (stdout.is_empty(), stderr.is_empty()) {
        (true, true) => String::new(),
        (true, false) => stderr,
        (false, true) => stdout,
        (false, false) => format!("{stdout}\n{stderr}"),
    }
}
