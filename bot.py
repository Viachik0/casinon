# bot.py (полная версия)
import asyncio
import json
import math
from typing import List

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
)

from config import get_settings
from storage.db import Database

# import game modules
from games import simple21, blackjack

# settings and db (use your existing config)
settings = get_settings()
db = Database(settings.db_path, starting_balance=settings.starting_balance)

router = Router()

# ----- UI helpers (buttons/kbs) -----
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Simple 21", callback_data="game:simple21")],
        [InlineKeyboardButton(text="🃏 Blackjack", callback_data="game:blackjack")],
        [InlineKeyboardButton(text="🎡 Roulette (coming soon)", callback_data="game:roulette")],
    ])


def back_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back", callback_data="nav:menu")]
    ])


def build_simple21_actions_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🃏 Hit", callback_data="simple21:hit"),
            InlineKeyboardButton(text="🛑 Stand", callback_data="simple21:stand"),
        ],
        [InlineKeyboardButton(text="⬅️ Menu", callback_data="nav:menu")]
    ])


def build_simple21_result_kb(last_bet: int, balance: int) -> InlineKeyboardMarkup:
    rows = []
    if last_bet <= balance:
        rows.append([InlineKeyboardButton(text=f"🔄 Same Bet ({last_bet})", callback_data=f"simple21:same:{last_bet}")])
    rows.append([InlineKeyboardButton(text="🎰 New Game", callback_data="game:simple21")])
    rows.append([InlineKeyboardButton(text="📋 Main Menu", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_blackjack_actions_kb(can_double: bool = False, can_split: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="🃏 Hit", callback_data="blackjack:hit"),
            InlineKeyboardButton(text="🛑 Stand", callback_data="blackjack:stand"),
        ]
    ]
    extra = []
    if can_double:
        extra.append(InlineKeyboardButton(text="💰 Double", callback_data="blackjack:double"))
    if extra:
        rows[0].extend(extra)
    if can_split:
        rows.append([InlineKeyboardButton(text="🔀 Split", callback_data="blackjack:split")])
    rows.append([InlineKeyboardButton(text="⬅️ Menu", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_blackjack_result_kb(original_bet: int, balance: int) -> InlineKeyboardMarkup:
    rows = []
    if original_bet <= balance:
        rows.append([InlineKeyboardButton(text=f"🔄 Same Bet ({original_bet})", callback_data=f"blackjack:same:{original_bet}")])
    rows.append([InlineKeyboardButton(text="🎰 New Game", callback_data="game:blackjack")])
    rows.append([InlineKeyboardButton(text="📋 Main Menu", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ----- Commands / navigation -----
@router.message(Command("start"))
async def cmd_start(msg: Message):
    user = await db.get_or_create_user(msg.from_user.id, msg.from_user.username)
    text = (
        f"🎰 <b>Casinon</b>\n\n"
        f"Welcome, <b>{msg.from_user.first_name or msg.from_user.username}</b>!\n"
        f"💰 Balance: {user['balance']} credits\n\n"
        "Choose a game:"
    )
    await msg.answer(text, reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "nav:menu")
async def nav_menu(cb: CallbackQuery):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    text = (
        f"🎰 <b>Casinon Main Menu</b>\n\n"
        f"💰 Balance: {user['balance']} credits\n\n"
        "Pick a game or check /balance"
    )
    await cb.message.edit_text(text, reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)
    await cb.answer()


@router.message(Command("balance"))
async def cmd_balance(msg: Message):
    user = await db.get_or_create_user(msg.from_user.id, msg.from_user.username)
    await msg.answer(f"💰 Balance: {user['balance']} credits", reply_markup=back_menu_kb())


@router.callback_query(F.data == "game:simple21")
async def game_simple21_entry(cb: CallbackQuery):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    if user["balance"] < settings.min_bet:
        await cb.message.edit_text(f"❌ Not enough balance. Minimum bet: {settings.min_bet}", reply_markup=back_menu_kb())
        await cb.answer()
        return
    
    build_bet_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💵 Bet {settings.min_bet}", callback_data=f"simple21:bet:{settings.min_bet}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="nav:menu")]
    ])
    
    await cb.message.edit_text(
        f"2️⃣1️⃣ <b>Simple 21</b>\n\n💰 Balance: {user['balance']} credits\n\n💵 Choose bet:",
        reply_markup=build_bet_kb,
        parse_mode=ParseMode.HTML
    )
    await cb.answer()

@router.callback_query(F.data.func(lambda d: d.startswith("simple21:bet:")))
async def simple21_place_bet(cb: CallbackQuery):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    try:
        bet = int(cb.data.split(":")[-1])
    except Exception:
        return await cb.answer("Invalid bet.", show_alert=True)
    if bet < settings.min_bet or bet > settings.max_bet or bet > user["balance"]:
        return await cb.answer("Invalid bet or insufficient balance.", show_alert=True)

    state = simple21.new_round_state(bet)
    success = await db.start_active_round(cb.from_user.id, "simple21", bet, json.dumps(state))
    if not success:
        return await cb.answer("Failed to start round.", show_alert=True)

    text = (
        f"2️⃣1️⃣ <b>Simple 21</b>\n"
        f"💵 <b>Bet:</b> {bet} credits (locked)\n\n"
        f"🃏 <b>Your hand:</b> {simple21.format_hand_with_total(state['player'])}\n"
        f"🀫 <b>Dealer shows:</b> {simple21.format_hand_with_total(state['dealer'])}"
    )
    await cb.message.edit_text(text, reply_markup=build_simple21_actions_kb(), parse_mode=ParseMode.HTML)
    await cb.answer("Round started!")


@router.callback_query(F.data == "simple21:hit")
async def simple21_hit(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "simple21":
        return await cb.answer("No active Simple 21 round.", show_alert=True)
    state = json.loads(active["state_json"])
    bet = active["bet"]

    # add card to player
    state, text_after, finished = simple21.player_hit_logic(state)

    # Save intermediate state
    await db.update_active_round(cb.from_user.id, json.dumps(state))

    # show player's new card first
    msg = (
        f"2️⃣1️⃣ <b>Simple 21</b>\n"
        f"💵 <b>Bet:</b> {bet} credits\n\n"
        f"🃏 <b>Your hand:</b> {simple21.format_hand_with_total(state['player'])}\n"
        f"🀫 <b>Dealer shows:</b> {simple21.format_hand_with_total(state['dealer'])}"
    )
    await cb.message.edit_text(msg, reply_markup=build_simple21_actions_kb(), parse_mode=ParseMode.HTML)

    # slight pause for effect
    await asyncio.sleep(0.3)

    if finished:
        # resolve loss immediately
        user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
        await db.resolve_active_round(cb.from_user.id, "loss", 0)
        # fetch updated user
        user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
        final_text = (
            f"💥 <b>BUST!</b>\n\n"
            f"🃏 <b>Your hand:</b> {simple21.format_hand_with_total(state['player'])}\n"
            f"🀫 <b>Dealer hand:</b> {simple21.format_hand_with_total(state['dealer'])}\n\n"
            f"❌ <b>Result:</b> Lost {bet} credits\n"
            f"💰 <b>Balance:</b> {user['balance']} credits"
        )
        await cb.message.edit_text(final_text, reply_markup=simple21.build_simple21_result_kb(bet, user["balance"]), parse_mode=ParseMode.HTML)
        await cb.answer("Bust!")
        return

    await cb.answer()


@router.callback_query(F.data == "simple21:stand")
async def simple21_stand(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "simple21":
        return await cb.answer("No active Simple 21 round.", show_alert=True)
    state = json.loads(active["state_json"])
    bet = active["bet"]

    # Dealer plays and we get final
    state, final_text, finished = simple21.player_stand_logic(state)

    # resolve according to result
    if state["result"] == "win":
        payout = 2 * bet  # follow simple21 payout convention
    elif state["result"] == "push":
        payout = bet
    else:
        payout = 0
    await db.resolve_active_round(cb.from_user.id, state["result"], payout)

    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    text = (
        f"{final_text}\n\n💰 <b>Balance:</b> {user['balance']} credits"
    )
    await cb.message.edit_text(text, reply_markup=simple21.build_simple21_result_kb(bet, user["balance"]), parse_mode=ParseMode.HTML)
    await cb.answer()


# ----- Blackjack: full flow (bet placing, hit/stand/double/split/surrender) -----
@router.callback_query(F.data == "game:blackjack")
async def game_blackjack_entry(cb: CallbackQuery):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    if user["balance"] < settings.min_bet:
        await cb.message.edit_text(f"❌ Not enough balance. Min bet: {settings.min_bet}", reply_markup=back_menu_kb())
        await cb.answer()
        return
    await cb.message.edit_text(
        f"🃏 <b>Blackjack</b>\n\n💰 Balance: {user['balance']} credits\n\n💵 Choose bet:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💵 Bet {settings.min_bet}", callback_data=f"blackjack:bet:{settings.min_bet}")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="nav:menu")]
        ]),
        parse_mode=ParseMode.HTML
    )
    await cb.answer()


@router.callback_query(F.data.func(lambda d: d.startswith("blackjack:bet:")))
async def blackjack_place_bet(cb: CallbackQuery):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    try:
        bet = int(cb.data.split(":")[-1])
    except Exception:
        return await cb.answer("Invalid bet.", show_alert=True)
    if bet < settings.min_bet or bet > settings.max_bet or bet > user["balance"]:
        return await cb.answer("Invalid bet or insufficient balance.", show_alert=True)

    state_obj = blackjack.BlackjackState(bet)
    state_json = state_obj.to_json()
    success = await db.start_active_round(cb.from_user.id, "blackjack", bet, state_json)
    if not success:
        return await cb.answer("Failed to start round.", show_alert=True)

    # Check immediate blackjack cases
    player_hand = state_obj.state["player_hands"][0]
    dealer = state_obj.state["dealer"]
    player_bj = state_obj.is_blackjack(player_hand)
    dealer_bj = state_obj.is_blackjack(dealer)

    # Build initial display
    text = (
        f"🃏 <b>Blackjack</b>\n"
        f"💵 Bet: {bet} credits (locked)\n\n"
        f"🃏 <b>Your hand:</b> {blackjack.format_hand_with_total(player_hand)}\n"
        f"🀫 <b>Dealer shows:</b> {state_obj.state['dealer_visible'][0]} {blackjack.HIDDEN_CARD}"
    )

    # If either has blackjack, reveal and resolve immediately
    if player_bj or dealer_bj:
        state_obj.reveal_dealer()
        state_obj.dealer_play()  # ensures dealer stays consistent (but dealer won't draw if bj)
        eval_res = state_obj.evaluate()
        # decide overall payout sum according to evaluate() outputs
        total_delta = 0
        overall_result = "push"
        for typ, payout, _msg in eval_res["results"]:
            if typ == "win":
                total_delta += payout
            elif typ == "push":
                total_delta += payout
            # loss adds 0
        # determine overall_result: if any win and no loss -> win etc.
        flags = {r[0] for r in eval_res["results"]}
        if "win" in flags and "loss" not in flags:
            overall_result = "win"
        elif "loss" in flags and "win" not in flags:
            overall_result = "loss"
        elif flags == {"push"}:
            overall_result = "push"
        else:
            overall_result = "mixed"
        await db.resolve_active_round(cb.from_user.id, overall_result, total_delta)
        user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
        # final text
        final_txt = f"🃏 <b>Blackjack — Round Complete</b>\n\n"
        for idx, (hand, (typ, payout, msg)) in enumerate(zip(state_obj.state["player_hands"], eval_res["results"])):
            final_txt += f"🎲 <b>Hand {idx+1}:</b> {blackjack.format_hand_with_total(hand)} — {msg}\n"
        final_txt += f"\n🀫 <b>Dealer:</b> {' '.join(state_obj.state['dealer'])} (total: {eval_res['dealer_total']})\n\n"
        final_txt += f"💰 <b>Balance:</b> {user['balance']} credits"
        await cb.message.edit_text(final_txt, reply_markup=build_blackjack_result_kb(bet, user["balance"]), parse_mode=ParseMode.HTML)
        await cb.answer()
        return

    # Normal flow: update DB, show actions
    await db.update_active_round(cb.from_user.id, state_json)
    can_double = True
    can_split = state_obj.can_split()
    await cb.message.edit_text(text, reply_markup=build_blackjack_actions_kb(can_double=can_double, can_split=can_split), parse_mode=ParseMode.HTML)
    await cb.answer("Blackjack started!")


# helper to load blackjack state object from DB row
def _load_bj_state(active_row) -> blackjack.BlackjackState:
    return blackjack.BlackjackState.from_json(active_row["state_json"])


@router.callback_query(F.data == "blackjack:hit")
async def blackjack_hit(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "blackjack":
        return await cb.answer("No active Blackjack round.", show_alert=True)
    state_obj = blackjack.BlackjackState.from_json(active["state_json"])
    ci = state_obj.state["current_hand"]
    hand = state_obj.current_hand()

    # draw for player
    card = state_obj.draw()
    hand.append(card)
    # update state
    state_obj.state["player_hands"][ci] = hand
    await db.update_active_round(cb.from_user.id, state_obj.to_json())

    # show player's hand immediately
    text = blackjack.format_hand_with_total(hand)
    await cb.message.edit_text(
        f"🃏 <b>Blackjack</b>\n\n🎲 <b>Your hand {ci+1}:</b> {blackjack.format_hand_with_total(hand)}\n🀫 <b>Dealer shows:</b> {' '.join(state_obj.state['dealer_visible'])}",
        reply_markup=build_blackjack_actions_kb(can_double=(len(hand) == 2), can_split=state_obj.can_split()),
        parse_mode=ParseMode.HTML
    )

    # small pause for drama
    await asyncio.sleep(0.3)

    # check bust
    if blackjack.calculate_hand_value(hand) > 21:
        # move to next or resolve
        state_obj.state["current_hand"] = ci + 1
        await db.update_active_round(cb.from_user.id, state_obj.to_json())
        # if more hands exist, continue, else dealer plays & resolve
        if state_obj.state["current_hand"] < len(state_obj.state["player_hands"]):
            next_hand = state_obj.state["player_hands"][state_obj.state["current_hand"]]
            await cb.message.edit_text(
                f"💥 <b>Hand busted</b>\n\n👉 Next hand {state_obj.state['current_hand']+1}: {blackjack.format_hand_with_total(next_hand)}\n🀫 Dealer shows: {' '.join(state_obj.state['dealer_visible'])}",
                reply_markup=build_blackjack_actions_kb(can_double=(len(next_hand)==2), can_split=(len(next_hand)==2 and next_hand[0][:-1]==next_hand[1][:-1])),
                parse_mode=ParseMode.HTML
            )
            await cb.answer("Busted this hand, moving on.")
            return
        # else resolve
        # reveal dealers and play
        state_obj.reveal_dealer()
        state_obj.dealer_play()
        eval_res = state_obj.evaluate()
        total_delta = sum(r[1] for r in eval_res["results"])
        flags = {r[0] for r in eval_res["results"]}
        overall = "mixed"
        if "win" in flags and "loss" not in flags:
            overall = "win"
        elif "loss" in flags and "win" not in flags:
            overall = "loss"
        elif flags == {"push"}:
            overall = "push"
        await db.resolve_active_round(cb.from_user.id, overall, total_delta)
        user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
        final_txt = f"🃏 <b>Blackjack — Round Complete</b>\n\n"
        for idx, (hand, (typ, payout, msg)) in enumerate(zip(state_obj.state["player_hands"], eval_res["results"])):
            final_txt += f"🎲 <b>Hand {idx+1}:</b> {blackjack.format_hand_with_total(hand)} — {msg}\n"
        final_txt += f"\n🀫 <b>Dealer:</b> {' '.join(state_obj.state['dealer'])} (total: {eval_res['dealer_total']})\n\n"
        final_txt += f"💰 <b>Balance:</b> {user['balance']} credits"
        await cb.message.edit_text(final_txt, reply_markup=build_blackjack_result_kb(state_obj.state['original_bet'], user['balance']), parse_mode=ParseMode.HTML)
        await cb.answer()
        return

    await cb.answer()


@router.callback_query(F.data == "blackjack:stand")
async def blackjack_stand(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "blackjack":
        return await cb.answer("No active Blackjack round.", show_alert=True)
    state_obj = blackjack.BlackjackState.from_json(active["state_json"])
    # advance to next hand
    state_obj.state["current_hand"] = state_obj.state["current_hand"] + 1
    await db.update_active_round(cb.from_user.id, state_obj.to_json())

    if state_obj.state["current_hand"] < len(state_obj.state["player_hands"]):
        next_hand = state_obj.state["player_hands"][state_obj.state["current_hand"]]
        await cb.message.edit_text(
            f"🃏 <b>Blackjack</b>\n\n👉 Now playing hand {state_obj.state['current_hand']+1}: {blackjack.format_hand_with_total(next_hand)}\n🀫 Dealer shows: {' '.join(state_obj.state['dealer_visible'])}",
            reply_markup=build_blackjack_actions_kb(can_double=(len(next_hand)==2), can_split=(len(next_hand)==2 and next_hand[0][:-1]==next_hand[1][:-1])),
            parse_mode=ParseMode.HTML
        )
        await cb.answer("Stand — next hand.")
        return

    # else all player hands done: dealer plays and resolve
    state_obj.reveal_dealer()
    state_obj.dealer_play()
    eval_res = state_obj.evaluate()
    total_delta = sum(r[1] for r in eval_res["results"])
    flags = {r[0] for r in eval_res["results"]}
    overall = "mixed"
    if "win" in flags and "loss" not in flags:
        overall = "win"
    elif "loss" in flags and "win" not in flags:
        overall = "loss"
    elif flags == {"push"}:
        overall = "push"
    await db.resolve_active_round(cb.from_user.id, overall, total_delta)
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    final_txt = f"🃏 <b>Blackjack — Round Complete</b>\n\n"
    for idx, (hand, (typ, payout, msg)) in enumerate(zip(state_obj.state["player_hands"], eval_res["results"])):
        final_txt += f"🎲 <b>Hand {idx+1}:</b> {blackjack.format_hand_with_total(hand)} — {msg}\n"
    final_txt += f"\n🀫 <b>Dealer:</b> {' '.join(state_obj.state['dealer'])} (total: {eval_res['dealer_total']})\n\n"
    final_txt += f"💰 <b>Balance:</b> {user['balance']} credits"
    await cb.message.edit_text(final_txt, reply_markup=build_blackjack_result_kb(state_obj.state['original_bet'], user['balance']), parse_mode=ParseMode.HTML)
    await cb.answer()


@router.callback_query(F.data == "blackjack:double")
async def blackjack_double(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "blackjack":
        return await cb.answer("No active Blackjack round.", show_alert=True)
    state_obj = blackjack.BlackjackState.from_json(active["state_json"])
    ci = state_obj.state["current_hand"]
    hand = state_obj.current_hand()
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    bet = state_obj.state["bets"][ci]
    # validate
    if len(hand) != 2:
        return await cb.answer("Double allowed only on first two cards.", show_alert=True)
    if bet > user["balance"]:
        return await cb.answer("Not enough balance to double.", show_alert=True)
    # take extra bet from user's balance via DB resolve later: here we just double the hand bet
    state_obj.state["bets"][ci] = bet * 2
    state_obj.state["doubled"][ci] = True
    # draw one card and move on
    card = state_obj.draw()
    hand.append(card)
    state_obj.state["player_hands"][ci] = hand
    state_obj.state["current_hand"] = ci + 1
    await db.update_active_round(cb.from_user.id, state_obj.to_json())

    # show double result and either next hand or resolve
    if state_obj.state["current_hand"] < len(state_obj.state["player_hands"]):
        next_hand = state_obj.state["player_hands"][state_obj.state["current_hand"]]
        await cb.message.edit_text(
            f"💰 <b>Double</b>\n\n🎲 Hand {ci+1}: {blackjack.format_hand_with_total(hand)}\n👉 Next hand {state_obj.state['current_hand']+1}: {blackjack.format_hand_with_total(next_hand)}\n🀫 Dealer shows: {' '.join(state_obj.state['dealer_visible'])}",
            reply_markup=build_blackjack_actions_kb(can_double=(len(next_hand)==2), can_split=(len(next_hand)==2 and next_hand[0][:-1]==next_hand[1][:-1])),
            parse_mode=ParseMode.HTML
        )
        await cb.answer("Doubled and moved to next hand.")
        return

    # else resolve:
    state_obj.reveal_dealer()
    state_obj.dealer_play()
    eval_res = state_obj.evaluate()
    total_delta = sum(r[1] for r in eval_res["results"])
    flags = {r[0] for r in eval_res["results"]}
    overall = "mixed"
    if "win" in flags and "loss" not in flags:
        overall = "win"
    elif "loss" in flags and "win" not in flags:
        overall = "loss"
    elif flags == {"push"}:
        overall = "push"
    await db.resolve_active_round(cb.from_user.id, overall, total_delta)
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    final_txt = f"🃏 <b>Blackjack — Round Complete</b>\n\n"
    for idx, (hand, (typ, payout, msg)) in enumerate(zip(state_obj.state["player_hands"], eval_res["results"])):
        final_txt += f"🎲 <b>Hand {idx+1}:</b> {blackjack.format_hand_with_total(hand)} — {msg}\n"
    final_txt += f"\n🀫 <b>Dealer:</b> {' '.join(state_obj.state['dealer'])} (total: {eval_res['dealer_total']})\n\n"
    final_txt += f"💰 <b>Balance:</b> {user['balance']} credits"
    await cb.message.edit_text(final_txt, reply_markup=build_blackjack_result_kb(state_obj.state['original_bet'], user['balance']), parse_mode=ParseMode.HTML)
    await cb.answer()


@router.callback_query(F.data == "blackjack:split")
async def blackjack_split(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "blackjack":
        return await cb.answer("No active Blackjack round.", show_alert=True)
    state_obj = blackjack.BlackjackState.from_json(active["state_json"])
    ci = state_obj.state["current_hand"]
    hand = state_obj.current_hand()
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    bet = state_obj.state["bets"][ci]
    # validate split
    if not state_obj.can_split():
        return await cb.answer("Cannot split this hand.", show_alert=True)
    if bet > user["balance"]:
        return await cb.answer("Not enough balance to split.", show_alert=True)
    # perform split: create two hands and draw one card for each
    card_a = hand[0]
    card_b = hand[1]
    new1 = [card_a, state_obj.draw()]
    new2 = [card_b, state_obj.draw()]
    state_obj.state["player_hands"][ci] = new1
    state_obj.state["player_hands"].insert(ci + 1, new2)
    state_obj.state["bets"].insert(ci + 1, bet)
    # extend flags arrays
    state_obj.state.setdefault("doubled", [])
    state_obj.state.setdefault("surrendered", [])
    state_obj.state["doubled"].insert(ci + 1, False)
    state_obj.state["surrendered"].insert(ci + 1, False)
    await db.update_active_round(cb.from_user.id, state_obj.to_json())
    await cb.message.edit_text(
        f"🔀 <b>Split</b>\n\n🎲 Hand 1: {blackjack.format_hand_with_total(new1)}\n🎲 Hand 2: {blackjack.format_hand_with_total(new2)}\n🀫 Dealer shows: {' '.join(state_obj.state['dealer_visible'])}",
        reply_markup=build_blackjack_actions_kb(can_double=True, can_split=False),
        parse_mode=ParseMode.HTML
    )
    await cb.answer("Split performed.")


# optional: surrender (with confirm flow)
@router.callback_query(F.data == "blackjack:surrender")
async def blackjack_surrender_confirm(cb: CallbackQuery):
    # We'll implement a two-step flow: first click shows confirm keyboard
    await cb.message.edit_text(
        "⚠️ Are you sure you want to Surrender? You'll get back half your bet for this hand.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Yes, surrender", callback_data="blackjack:surrender:confirm"),
             InlineKeyboardButton(text="❌ No", callback_data="nav:menu")]
        ])
    )
    await cb.answer()


@router.callback_query(F.data == "blackjack:surrender:confirm")
async def blackjack_surrender_execute(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "blackjack":
        return await cb.answer("No active Blackjack round.", show_alert=True)
    state_obj = blackjack.BlackjackState.from_json(active["state_json"])
    ci = state_obj.state["current_hand"]
    state_obj.state.setdefault("surrendered", [])
    # mark surrendered and move on
    if ci < len(state_obj.state["surrendered"]):
        state_obj.state["surrendered"][ci] = True
    else:
        # extend if necessary
        while len(state_obj.state["surrendered"]) <= ci:
            state_obj.state["surrendered"].append(False)
        state_obj.state["surrendered"][ci] = True
    # move to next hand or resolve
    state_obj.state["current_hand"] = ci + 1
    await db.update_active_round(cb.from_user.id, state_obj.to_json())

    if state_obj.state["current_hand"] < len(state_obj.state["player_hands"]):
        next_hand = state_obj.state["player_hands"][state_obj.state["current_hand"]]
        await cb.message.edit_text(
            f"⚠️ Surrendered hand {ci+1}. Next: {blackjack.format_hand_with_total(next_hand)}\n🀫 Dealer shows: {' '.join(state_obj.state['dealer_visible'])}",
            reply_markup=build_blackjack_actions_kb(can_double=(len(next_hand)==2), can_split=(len(next_hand)==2 and next_hand[0][:-1]==next_hand[1][:-1])),
            parse_mode=ParseMode.HTML
        )
        await cb.answer("Surrendered this hand.")
        return

    # else resolve
    state_obj.reveal_dealer()
    state_obj.dealer_play()
    eval_res = state_obj.evaluate()
    total_delta = sum(r[1] for r in eval_res["results"])
    flags = {r[0] for r in eval_res["results"]}
    overall = "mixed"
    if "win" in flags and "loss" not in flags:
        overall = "win"
    elif "loss" in flags and "win" not in flags:
        overall = "loss"
    elif flags == {"push"}:
        overall = "push"
    await db.resolve_active_round(cb.from_user.id, overall, total_delta)
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    final_txt = f"🃏 <b>Blackjack — Round Complete</b>\n\n"
    for idx, (hand, (typ, payout, msg)) in enumerate(zip(state_obj.state["player_hands"], eval_res["results"])):
        final_txt += f"🎲 <b>Hand {idx+1}:</b> {blackjack.format_hand_with_total(hand)} — {msg}\n"
    final_txt += f"\n🀫 <b>Dealer:</b> {' '.join(state_obj.state['dealer'])} (total: {eval_res['dealer_total']})\n\n"
    final_txt += f"💰 <b>Balance:</b> {user['balance']} credits"
    await cb.message.edit_text(final_txt, reply_markup=build_blackjack_result_kb(state_obj.state['original_bet'], user['balance']), parse_mode=ParseMode.HTML)
    await cb.answer()


# ----- Coming soon for roulette -----
@router.callback_query(F.data == "game:roulette")
async def game_roulette(cb: CallbackQuery):
    await cb.message.edit_text("🎡 Roulette — coming soon! Stay tuned.", reply_markup=back_menu_kb())
    await cb.answer()


# ----- Entrypoint -----
async def main():
    await db.init()
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())