from src.statistics import wilson_interval, bh_adjust


def test_metrics_ranges():
    low,high=wilson_interval(50,100)
    assert 0<low<.5<high<1
    adjusted=bh_adjust([.01,.04,.2])
    assert adjusted[0]<=adjusted[1]<=adjusted[2]

