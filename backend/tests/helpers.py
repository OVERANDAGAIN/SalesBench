from uuid import uuid4

from salesbench_engine.actions import CreateListing, Procure, Purchase, Wait
from salesbench_engine.models import Account, Buyer, Experiment, MarketSetup, Product, Seller, Supplier, SupplierOffer
from salesbench_engine.runner.codec import action_data, data


def setup_market(two_sellers=False):
    sellers = (Seller("seller", "Seller"), Seller("other-seller", "Other seller")) if two_sellers else (Seller("seller", "Seller"),)
    buyers = (Buyer("buyer", "Buyer"), Buyer("other-buyer", "Other buyer"))
    return MarketSetup(Experiment("platform-test", 7), (Supplier("supplier", "Supplier"),), sellers, buyers,
                       (Product("cup", "Cup"),), (SupplierOffer("cups", "supplier", "cup", 100, 10),),
                       (Account("supplier", 0), *(Account(a.id, 1000) for a in (*sellers, *buyers))))


def create_market(service, *, two_sellers=False, ticks=1):
    return service.create("test-" + uuid4().hex, data(setup_market(two_sellers)), {"max_rounds": 1, "ticks_per_round": ticks})


def request_for(observation, actions, request_id=None):
    return {"request_id": request_id or "batch-" + uuid4().hex,
            "observation_version": observation["published_version"],
            "opportunity_id": observation["opportunity"]["opportunity_id"],
            "actions": [action_data(a) for a in actions]}


def submit_wave(service, created, script):
    requests = {}
    for actor, token in created["actor_tokens"].items():
        obs = service.observe(created["session_id"], token)
        if obs["opportunity"]:
            request = request_for(obs, script(actor, obs))
            service.submit(created["session_id"], token, request)
            requests[actor] = request
    return requests


def prepare_buyers(service, created, *, seller_actions=None):
    sid = created["session_id"]
    submit_wave(service, created, lambda actor, obs: (Procure("cups", 1, 100),))
    assert service.run_ready(sid)["runtime"]["published_version"] == 1
    submit_wave(service, created, seller_actions or (lambda actor, obs: (CreateListing(actor + "/cup", "cup", 300, "TEST"),)))
    assert service.run_ready(sid)["runtime"]["published_version"] == 2


def queue_purchases(service, created):
    return submit_wave(service, created, lambda actor, obs: (Purchase("seller/cup", 1, 300, 1),))
