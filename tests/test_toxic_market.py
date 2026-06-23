import numpy as np
from market_maker_lab.scenarios import build_scenario_model
from market_maker_lab.market_primitives import Quote

def test_schedules_reset_and_advance():
    m=build_scenario_model("regime_switching",10); assert m.current_volatility==.55
    m.sample_interval(Quote(99.95,100.05,5,5),100,0,.1,np.random.default_rng(1),np.random.default_rng(2))
    assert m.current_volatility==.55
    m.reset(); assert m.current_volatility==.55

def test_no_toxic_label_in_clean():
    m=build_scenario_model("clean",10)
    out=m.sample_interval(Quote(99.95,100.05,100,100),100,0,1,np.random.default_rng(1),np.random.default_rng(2))
    assert out.toxic_bid_quantity==0 and out.toxic_ask_quantity==0

def test_negative_signal_links_bid_flow_and_negative_information():
    m=build_scenario_model("toxic",20); mr=np.random.default_rng(10); fr=np.random.default_rng(20)
    for _ in range(20):
        o=m.sample_interval(Quote(99.95,100.05,20,20),100,0,.05,mr,fr)
        if o.latent_signal<0:
            assert o.bid_intensity>o.ask_intensity and o.information_move<0
            break
    else: raise AssertionError("No negative signal sampled")

def test_stress_contains_jump():
    m=build_scenario_model("stress",20); jumps=[]
    mr=np.random.default_rng(1); fr=np.random.default_rng(2); p=100
    for i in range(20):
        o=m.sample_interval(Quote(p-.05,p+.05,1,1),p,i/20,.05,mr,fr); jumps.append(o.jump_move); p=o.next_mid_price
    assert min(jumps)<0
