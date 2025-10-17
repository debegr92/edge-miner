# About
**EdgeMiner** is a software to load historical charts and take screenshots of daytrading setups using the **Interactive Brokers TWS/Gateway API**.

> _Plan the trade, follow the plan!_

![edge-miner](doc/img/edge-miner.png)

# Install
This project comes with a **stable build** of the **TWS API**. If you want to build the API by your own, follow the [installation guide](./doc/install-api.md) and replace wheel file in the **dist** folder.
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

# ToDo
- [ ] Add tagging options
- [ ] Build database for all setups
