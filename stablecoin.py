# Python USD - Experimental Risky Lamden Fully Decentralized Stable Coin
# Check collateralization TAU to PUSD by using get_current_backing_ratio()
# !! If it's 1 everything is fine and if > 1.5 it's amazing and overcollateralized !!

# You can exchange TAU to PUSD and PUSD to TAU at any point at the same ratio that LUSD-TAU is at using tau_to_pusd() or pusd_to_tau()
# Don't forget to approve TAU to con_pusd or tau_to_pusd() exchange function doesn't work or just use the Swap dApp UI
# Difference to LUSD is that PYUSD is collateralized by TAU on this chain instead of USDT
# No Slippage Stablecoin Swap available at https://pusd.to

import currency as tau

I = importlib

balances = Hash(default_value=0)
allowances = Hash(default_value=0)
metadata = Hash(default_value='')

total_supply = Variable()


@construct
def seed():
    metadata['token_name'] = "Python USD"
    metadata['token_symbol'] = "PUSD"
    metadata['dex'] = 'con_rocketswap_official_v1_1'
    metadata['lusd'] = 'con_lusd_lst001'
    metadata['dev_addr'] = 'pusd_dev_addr'

    metadata['dev_tax'] = 0.5  # Developer tax
    metadata['mnt_tax'] = 0.5  # Minting tax
    metadata['liq_tax'] = 1  # Liquidity tax

    metadata['operators'] = [
        'ae7d14d6d9b8443f881ba6244727b69b681010e782d4fe482dbfb0b6aca02d5d',
        '6a9004cbc570592c21879e5ee319c754b9b7bf0278878b1cc21ac87eed0ee38d'
    ]

    total_supply.set(0)

@export
def change_metadata(key: str, value: Any):
    assert key.lower() != 'operators', 'Can not change owners'
    assert value, 'Parameter "value" can not be empty'

    metadata[key][ctx.caller] = value

    owner1 = metadata['operators'][0]
    owner2 = metadata['operators'][1]

    if metadata[key][owner1] == metadata[key][owner2]:
        metadata[key] = value

        metadata[key][owner1] = ''
        metadata[key][owner2] = ''
    
    assert_owner()

@export
def transfer(amount: float, to: str):
    assert amount > 0, 'Cannot send negative balances!'
    assert balances[ctx.caller] >= amount, 'Not enough coins to send!'

    balances[ctx.caller] -= amount
    balances[to] += amount

@export
def approve(amount: float, to: str):
    assert amount > 0, 'Cannot send negative balances!'
    
    allowances[ctx.caller, to] += amount

@export
def transfer_from(amount: float, to: str, main_account: str):
    assert amount > 0, 'Cannot send negative balances!'
    assert allowances[main_account, ctx.caller] >= amount, f'You approved {allowances[main_account, ctx.caller]} but need {amount}'
    assert balances[main_account] >= amount, 'Not enough coins to send!'
    
    allowances[main_account, ctx.caller] -= amount
    balances[main_account] -= amount
    balances[to] += amount

@export
def tau_to_pusd(tau_amount: float):
    assert tau_amount > 0, 'Cannot send negative balances!'

    dev_amount = tau_amount / 100 * metadata['dev_tax']
    mnt_amount = tau_amount / 100 * metadata['mnt_tax']

    tau.transfer_from(amount=tau_amount, to=ctx.this, main_account=ctx.caller)
    tau.transfer(amount=dev_amount, to=metadata['dev_addr'])  # TODO: TEST

    prices = ForeignHash(foreign_contract=metadata['dex'], foreign_name='prices')

    pusd_amount = (tau_amount / prices[metadata['lusd']]) - dev_amount - mnt_amount

    balances[ctx.caller] += pusd_amount
    total_supply.set(total_supply.get() + pusd_amount)

@export
def pusd_to_tau(pusd_amount: float):
    assert pusd_amount > 0, 'Cannot send negative balances!'

    prices = ForeignHash(foreign_contract=metadata['dex'], foreign_name='prices')

    liq_amount = pusd_amount / 100 * metadata['liq_tax']
    tau_amount = (pusd_amount - liq_amount) * prices[metadata['lusd']]

    tau.transfer(amount=tau_amount, to=ctx.caller)
    
    balances[ctx.this] += liq_amount
    balances[ctx.caller] -= pusd_amount
    
    total_supply.set(total_supply.get() - pusd_amount)

    if liq_amount >= 10:
        add_liquidity(liq_amount)

def add_liquidity(pusd_amount: float):
    approve(amount=pusd_amount, to=metadata['dex'])
    tau_amount = I.import_module(metadata['dex']).sell(contract=ctx.this, token_amount=pusd_amount / 2)

    tau.approve(amount=tau_amount, to=metadata['dex'])
    I.import_module(metadata['dex']).add_liquidity(contract=ctx.this, currency_amount=pusd_amount)

@export
def get_current_backing_ratio():  # > 1 = Good
    prices = ForeignHash(foreign_contract=metadata['dex'], foreign_name='prices')
    return ((tau.balance_of(ctx.this) * (1 / prices[metadata['lusd']])) / circulating_supply())

@export
def migrate_tau(contract: str, amount: float):
    approved_action('migrate_tau', contract, amount)

    tau.transfer(amount=amount, to=contract, main_account=ctx.this)
    assert_owner()

@export
def migrate_pusd(contract: str, amount: float):
    assert amount > 0, 'Cannot send negative balances!'
    assert balances[ctx.this] >= amount, 'Not enough coins to send!'

    approved_action('migrate_pusd', contract, amount)

    balances[ctx.this] -= amount
    balances[contract] += amount
    assert_owner()

@export
def migrate_lp(contract: str, amount: float):
    approved_action('migrate_lp', contract, amount)

    dex = I.import_module(metadata['dex'])
    dex.approve_liquidity(ctx.this, contract, amount)
    dex.transfer_liquidity(ctx.this, contract, amount)
    assert_owner()

@export
def withdraw_dev_funds(amount: float):
    assert amount > 0, 'Cannot send negative balances!'
    assert balances[metadata['dev_addr']] >= amount, 'Not enough coins to send!'

    approved_action('withdraw_dev_funds', ctx.caller, amount)

    balances[metadata['dev_addr']] -= amount
    balances[ctx.caller] += amount
    assert_owner()

def approved_action(action: str, contract: str, amount: float):
    owner1 = metadata['operators'][0]
    owner2 = metadata['operators'][1]

    assert metadata[action][owner1] = f'{contract}{amount}', f'Wrong metadata for {owner1}'
    assert metadata[action][owner2] = f'{contract}{amount}', f'Wrong metadata for {owner2}'

@export
def circulating_supply():
    return f'{total_supply.get() - balances[ctx.this]}'

@export
def total_supply():
    return f'{total_supply.get()}'

def assert_owner():
    assert ctx.caller in metadata['operators'], 'Only executable by operators!'
