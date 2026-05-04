use rand::prelude::*;
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Course {
    pub id: String,
    pub workload_hours: u32,
    pub expected_demand: u32,
    pub requires_lab: bool,
    pub criticality: u32,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Professor {
    pub id: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Room {
    pub id: String,
    pub capacity: u32,
    pub kind: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct TimeSlot {
    pub id: String,
    pub day: u32,
    pub start_minute: u32,
    pub end_minute: u32,
}

impl TimeSlot {
    fn hours(&self) -> f64 {
        (self.end_minute - self.start_minute) as f64 / 60.0
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Qualification {
    pub professor_id: String,
    pub course_id: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Contract {
    pub professor_id: String,
    pub min_hours: f64,
    pub max_hours: f64,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct CoursePreference {
    pub professor_id: String,
    pub course_id: String,
    pub preference: i32,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct OptimizationInput {
    pub courses: Vec<Course>,
    pub professors: Vec<Professor>,
    pub rooms: Vec<Room>,
    pub slots: Vec<TimeSlot>,
    pub qualifications: Vec<Qualification>,
    pub contracts: Vec<Contract>,
    pub preferences: Vec<CoursePreference>,
    pub population: Option<usize>,
    pub generations: Option<usize>,
    pub seed: Option<u64>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Assignment {
    pub course_id: String,
    pub professor_id: String,
    pub room_id: String,
    pub time_slot_id: String,
    pub session_index: u32,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Objectives {
    pub hard_conflicts: f64,
    pub preference_loss: f64,
    pub load_imbalance: f64,
    pub room_waste: f64,
    pub coverage_loss: f64,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct OptimizationOutput {
    pub assignments: Vec<Assignment>,
    pub objectives: Objectives,
    pub score: f64,
    pub generations: usize,
    pub population: usize,
}

#[derive(Clone)]
struct Individual {
    assignments: Vec<Assignment>,
    objectives: Objectives,
    score: f64,
}

pub fn optimize(input: OptimizationInput) -> OptimizationOutput {
    let population_size = input.population.unwrap_or(256).max(16);
    let generations = input.generations.unwrap_or(160).max(1);
    let seed = input.seed.unwrap_or(42);
    let ctx = Context::new(input);

    let mut population: Vec<Individual> = (0..population_size)
        .into_par_iter()
        .map(|idx| {
            let mut rng = StdRng::seed_from_u64(seed + idx as u64 * 7919);
            let assignments = random_assignments(&ctx, &mut rng);
            evaluate(&ctx, assignments)
        })
        .collect();

    for generation in 0..generations {
        population.par_sort_unstable_by(|left, right| left.score.total_cmp(&right.score));
        let elite_count = (population_size / 8).max(2);
        let elites = population[..elite_count].to_vec();
        let children: Vec<Individual> = (0..(population_size - elite_count))
            .into_par_iter()
            .map(|idx| {
                let mut rng = StdRng::seed_from_u64(seed + generation as u64 * 104_729 + idx as u64);
                let parent = elites.choose(&mut rng).expect("elite missing");
                let assignments = mutate(&ctx, &parent.assignments, &mut rng);
                evaluate(&ctx, assignments)
            })
            .collect();
        population = elites.into_iter().chain(children).collect();
    }

    population.sort_by(|left, right| left.score.total_cmp(&right.score));
    let best = population.remove(0);
    OptimizationOutput {
        assignments: best.assignments,
        objectives: best.objectives,
        score: best.score,
        generations,
        population: population_size,
    }
}

struct Context {
    courses: Vec<Course>,
    rooms: Vec<Room>,
    slots: Vec<TimeSlot>,
    qualifications: HashMap<String, Vec<String>>,
    contracts: HashMap<String, Contract>,
    preferences: HashMap<(String, String), i32>,
}

impl Context {
    fn new(input: OptimizationInput) -> Self {
        let mut qualifications: HashMap<String, Vec<String>> = HashMap::new();
        for item in input.qualifications {
            qualifications
                .entry(item.course_id)
                .or_default()
                .push(item.professor_id);
        }
        let contracts = input
            .contracts
            .into_iter()
            .map(|contract| (contract.professor_id.clone(), contract))
            .collect();
        let preferences = input
            .preferences
            .into_iter()
            .map(|preference| {
                (
                    (preference.professor_id, preference.course_id),
                    preference.preference,
                )
            })
            .collect();
        Self {
            courses: input.courses,
            rooms: input.rooms,
            slots: input.slots,
            qualifications,
            contracts,
            preferences,
        }
    }
}

fn random_assignments(ctx: &Context, rng: &mut StdRng) -> Vec<Assignment> {
    let mut assignments = Vec::new();
    for course in &ctx.courses {
        let sessions = ((course.workload_hours as f64) / 2.0).ceil().max(1.0) as u32;
        for session_index in 0..sessions {
            if let Some(assignment) = random_assignment(ctx, course, session_index, rng) {
                assignments.push(assignment);
            }
        }
    }
    assignments
}

fn random_assignment(
    ctx: &Context,
    course: &Course,
    session_index: u32,
    rng: &mut StdRng,
) -> Option<Assignment> {
    let professor_id = ctx.qualifications.get(&course.id)?.choose(rng)?.clone();
    let room = ctx
        .rooms
        .iter()
        .filter(|room| {
            room.capacity >= course.expected_demand && (!course.requires_lab || room.kind == "lab")
        })
        .collect::<Vec<_>>()
        .choose(rng)?
        .to_owned();
    let slot = ctx.slots.choose(rng)?;
    Some(Assignment {
        course_id: course.id.clone(),
        professor_id,
        room_id: room.id.clone(),
        time_slot_id: slot.id.clone(),
        session_index,
    })
}

fn mutate(ctx: &Context, assignments: &[Assignment], rng: &mut StdRng) -> Vec<Assignment> {
    let mut mutated = assignments.to_vec();
    if mutated.is_empty() {
        return random_assignments(ctx, rng);
    }
    let mutations = rng.gen_range(1..=3);
    for _ in 0..mutations {
        let index = rng.gen_range(0..mutated.len());
        if let Some(course) = ctx
            .courses
            .iter()
            .find(|course| course.id == mutated[index].course_id)
        {
            if let Some(next) = random_assignment(ctx, course, mutated[index].session_index, rng) {
                mutated[index] = next;
            }
        }
    }
    mutated
}

fn evaluate(ctx: &Context, assignments: Vec<Assignment>) -> Individual {
    let mut hard_conflicts = 0.0;
    let mut professor_slot = HashSet::new();
    let mut room_slot = HashSet::new();
    let mut professor_load: HashMap<String, f64> = HashMap::new();
    let mut room_waste = 0.0;
    let mut preference = 0.0;
    let course_by_id: HashMap<&str, &Course> =
        ctx.courses.iter().map(|course| (course.id.as_str(), course)).collect();
    let room_by_id: HashMap<&str, &Room> =
        ctx.rooms.iter().map(|room| (room.id.as_str(), room)).collect();
    let slot_by_id: HashMap<&str, &TimeSlot> =
        ctx.slots.iter().map(|slot| (slot.id.as_str(), slot)).collect();

    for assignment in &assignments {
        if !professor_slot.insert((&assignment.professor_id, &assignment.time_slot_id)) {
            hard_conflicts += 1.0;
        }
        if !room_slot.insert((&assignment.room_id, &assignment.time_slot_id)) {
            hard_conflicts += 1.0;
        }
        let Some(course) = course_by_id.get(assignment.course_id.as_str()) else {
            hard_conflicts += 1.0;
            continue;
        };
        let Some(room) = room_by_id.get(assignment.room_id.as_str()) else {
            hard_conflicts += 1.0;
            continue;
        };
        let Some(slot) = slot_by_id.get(assignment.time_slot_id.as_str()) else {
            hard_conflicts += 1.0;
            continue;
        };
        if room.capacity < course.expected_demand {
            hard_conflicts += 1.0;
        }
        if course.requires_lab && room.kind != "lab" {
            hard_conflicts += 1.0;
        }
        *professor_load.entry(assignment.professor_id.clone()).or_default() += slot.hours();
        room_waste += room.capacity.saturating_sub(course.expected_demand) as f64;
        preference += ctx
            .preferences
            .get(&(assignment.professor_id.clone(), assignment.course_id.clone()))
            .copied()
            .unwrap_or_default() as f64;
    }

    for (professor_id, contract) in &ctx.contracts {
        let load = professor_load.get(professor_id).copied().unwrap_or_default();
        if load < contract.min_hours || load > contract.max_hours {
            hard_conflicts += 1.0;
        }
    }

    let required: u32 = ctx
        .courses
        .iter()
        .map(|course| ((course.workload_hours as f64) / 2.0).ceil().max(1.0) as u32)
        .sum();
    let coverage_loss = if required == 0 {
        0.0
    } else {
        (1.0 - assignments.len() as f64 / required as f64).max(0.0) * 100.0
    };
    let loads = professor_load.values().copied().collect::<Vec<_>>();
    let load_imbalance = stddev(&loads);
    let preference_loss = (40.0 - preference).max(0.0);
    let objectives = Objectives {
        hard_conflicts,
        preference_loss,
        load_imbalance,
        room_waste,
        coverage_loss,
    };
    let score = hard_conflicts * 100_000.0
        + coverage_loss * 2_000.0
        + preference_loss * 8.0
        + load_imbalance * 30.0
        + room_waste * 0.15;
    Individual {
        assignments,
        objectives,
        score,
    }
}

fn stddev(values: &[f64]) -> f64 {
    if values.len() < 2 {
        return 0.0;
    }
    let mean = values.iter().sum::<f64>() / values.len() as f64;
    let variance = values
        .iter()
        .map(|value| {
            let delta = value - mean;
            delta * delta
        })
        .sum::<f64>()
        / values.len() as f64;
    variance.sqrt()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn optimizer_returns_assignments() {
        let input = OptimizationInput {
            courses: vec![Course {
                id: "c1".to_string(),
                workload_hours: 4,
                expected_demand: 20,
                requires_lab: false,
                criticality: 5,
            }],
            professors: vec![Professor {
                id: "p1".to_string(),
            }],
            rooms: vec![Room {
                id: "r1".to_string(),
                capacity: 30,
                kind: "lecture".to_string(),
            }],
            slots: vec![
                TimeSlot {
                    id: "s1".to_string(),
                    day: 0,
                    start_minute: 480,
                    end_minute: 600,
                },
                TimeSlot {
                    id: "s2".to_string(),
                    day: 0,
                    start_minute: 600,
                    end_minute: 720,
                },
            ],
            qualifications: vec![Qualification {
                professor_id: "p1".to_string(),
                course_id: "c1".to_string(),
            }],
            contracts: vec![Contract {
                professor_id: "p1".to_string(),
                min_hours: 2.0,
                max_hours: 6.0,
            }],
            preferences: vec![CoursePreference {
                professor_id: "p1".to_string(),
                course_id: "c1".to_string(),
                preference: 5,
            }],
            population: Some(32),
            generations: Some(8),
            seed: Some(7),
        };

        let output = optimize(input);
        assert_eq!(output.assignments.len(), 2);
    }
}

