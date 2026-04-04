$ErrorActionPreference = "Stop"

function Have-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

if (Have-Command "py") {
    py -m pip install -r requirements.txt
    py -m streamlit run app.py
}
elseif (Have-Command "python") {
    python -m pip install -r requirements.txt
    python -m streamlit run app.py
}
else {
    throw "Python not found. Install Python 3.10+ and rerun."
}
