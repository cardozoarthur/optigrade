use std::io::{self, Read};

use optigrade_optimizer::{optimize, OptimizationInput};

fn main() {
    let mut buffer = String::new();
    io::stdin()
        .read_to_string(&mut buffer)
        .expect("failed to read optimizer input");
    let input: OptimizationInput =
        serde_json::from_str(&buffer).expect("failed to parse optimizer input");
    let output = optimize(input);
    println!(
        "{}",
        serde_json::to_string(&output).expect("failed to serialize optimizer output")
    );
}

