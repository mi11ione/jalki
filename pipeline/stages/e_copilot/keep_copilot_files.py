"""s11_answers.py and s03_final.py use the same two file names. Keep the first pass under its own name, because s03_final
reuses its rubric answers and evidence and the bundle reads its results."""
import shutil

from ccn_paths import stage_dir

H = stage_dir("e_copilot")
shutil.copyfile(H / "E_answers_submission.csv", H / "e_copilot_answers.csv")
shutil.copyfile(H / "results.json", H / "e_copilot_results.json")
print("kept e_copilot_answers.csv and e_copilot_results.json")
