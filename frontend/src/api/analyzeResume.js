export async function analyzeResume(file, jobDescription = "") {
  const formData = new FormData();
  formData.append("file", file);
  if (jobDescription.trim()) {
    formData.append("job_description", jobDescription.trim());
  }

  const response = await fetch("http://localhost:8000/analyze", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Server error — please try again");
  }

  return response.json();
}
