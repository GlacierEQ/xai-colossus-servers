import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from rack_planner import Node, Rack, place, ANSWER

def test_place():
    r = place([Node("a", 5)], [Rack("r1", 10)])
    assert r["ok"] and r["plan"][0]["rack"]=="r1" and r["answer"]==ANSWER

if __name__=="__main__":
    test_place(); print("ok")
