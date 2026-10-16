"""Local production composition using original owned equipment/effect fields.

Stat-to-yield and additive/multiplicative stacking are documented restoration
policies. Item job restrictions and each modifier come from the user's APK.
Final per-job values are emitted once; no duplicate native global boost added.
"""
import math
from . import effects


def _number(value, default=0):
    if isinstance(value,bool):return default
    try:value=float(value)
    except (ValueError,TypeError,OverflowError):return default
    return value if math.isfinite(value) else default


def parameters(person, job_id, rules, data=None, now=0, *, gather_seconds=8, travel_seconds=4):
    stat='intelligence' if job_id==20 else 'strength'
    value=_number(person.get('stats',{}).get(stat,10),10)
    modifier,time_modifier=0.0,0.0
    multiplier,time_multiplier=1.0,1.0
    groups=set(rules.get('jobs',{}).get(str(job_id),{}).get('boost_groups',[]))
    for ident,item in person.get('items',{}).items():
        if _number(item.get('count'))<=0:continue
        rule=rules.get('items',{}).get(str(ident),{})
        if int(rule.get('type',-1))!=5:continue
        ids=rule.get('job_ids',[]);item_groups=set(rule.get('job_boost_groups',[]))
        if (ids or item_groups) and job_id not in ids and not groups.intersection(item_groups):continue
        value+=_number(rule.get(stat))
        modifier+=_number(rule.get('production_rate_modifier'))
        multiplier*=max(.001,_number(rule.get('production_rate_multiplier',1),1))
        time_modifier+=_number(rule.get('production_time_modifier'))
        time_multiplier*=max(.001,_number(rule.get('production_time_multiplier',1),1))
    if data is not None:
        overlay=effects.production_modifiers(data,person,job_id,now,rules)
        modifier+=overlay['rate_modifier'];multiplier*=overlay['rate_multiplier']
        time_modifier+=overlay['time_modifier'];time_multiplier*=overlay['time_multiplier']
    # Requested local balance: two basic resources per trip, before existing
    # strength/tool/booster bonuses. Research keeps its separate one-point base.
    base=min(5.0,(2.0 if job_id in (16,17,18) else 1.0)+max(0,value-10)/100)
    rate=max(.001,(base+modifier)*multiplier)
    gather=max(1,math.ceil(max(.001,(gather_seconds+time_modifier)*time_multiplier)))
    return {'gather_rate':rate,'gather_time':gather,'trip_time':gather+travel_seconds}
