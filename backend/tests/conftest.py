import os


# Normal unit tests never call external models. Gemini behavior uses mocks.
os.environ["SUMMARY_PROVIDER"] = "template"
