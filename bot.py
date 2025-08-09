import asyncio
from typing import Set

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
from games import blackjack

settings = get_settings()
db = Database(settings.db_path, starting_balance=settings.starting_balance)
router = Router()

# ====================================================================================
# Keyboards
# ====================================================================================

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🃏 Blackjack", callback_data="game:blackjack")],
        [InlineKeyboardButton(text="🎡 Roulette (coming soon)", callback_data="game:roulette")],
    ])

def back_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back", callback_data="nav:menu")]
    ])

def build_blackjack_actions_kb(can_double: bool, can_split: bool) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(text="🃏 Hit", callback_data="blackjack:hit"),
        InlineKeyboardButton(text="🛑 Stand", callback_data="blackjack:stand"),
    ]
    if can_double:
        row.append(InlineKeyboardButton(text="💰 Double", callback_data="blackjack:double"))
    rows = [row]
    if can_split:
        rows.append([InlineKeyboardButton(text="🔀 Split", callback_data="blackjack:split")])
    rows.append([InlineKeyboardButton(text="⚠️ Surrender", callback_data="blackjack:surrender")])
    rows.append([InlineKeyboardButton(text="⬅️ Menu", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def build_blackjack_result_kb(original_bet: int, balance: int) -> InlineKeyboardMarkup:
    rows = []
    if original_bet <= balance:
        rows.append([InlineKeyboardButton(text=f"🔄 Same Bet ({original_bet})", callback_data=f"blackjack:same:{original_bet}")])
    rows.append([InlineKeyboardButton(text="🎰 New Blackjack", callback_data="game:blackjack")])
    rows.append([InlineKeyboardButton(text="📋 Main Menu", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ====================================================================================
# General / Navigation
# ====================================================================================

@router.message(Command("start"))
async def cmd_start(msg: Message):
    user = await db.get_or_create_user(msg.from_user.id, msg.from_user.username)
    await msg.answer(
        f"🎰 <b>Casinon</b>\n\nWelcome, <b>{msg.from_user.first_name or msg.from_user.username}</b>!\n"
        f"💰 Balance: {user['balance']} credits\n\nChoose a game:",
        reply_markup=main_menu_kb(),
        parse_mode=ParseMode.HTML
    )

@router.message(Command("balance"))
async def cmd_balance(msg: Message):
    user = await db.get_or_create_user(msg.from_user.id, msg.from_user.username)
    await msg.answer(f"💰 Balance: {user['balance']} credits", reply_markup=back_menu_kb())

@router.callback_query(F.data == "nav:menu")
async def nav_menu(cb: CallbackQuery):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    await cb.message.edit_text(
        f"🎰 <b>Casinon Main Menu</b>\n\n💰 Balance: {user['balance']} credits",
        reply_markup=main_menu_kb(),
        parse_mode=ParseMode.HTML
    )
    await cb.answer()

# ====================================================================================
# Active Round Utilities
# ====================================================================================

async def _cancel_active_round(tg_id: int, refund: bool = True) -> bool:
    active = await db.get_active_round(tg_id)
    if not active:
        return False
    bet = active["bet"]
    await db.delete_active_round(tg_id)
    if refund and bet > 0:
        await db.update_balance(tg_id, bet)
    return True

@router.message(Command("cancel"))
async def cmd_cancel(msg: Message):
    canceled = await _cancel_active_round(msg.from_user.id, refund=True)
    if canceled:
        user = await db.get_or_create_user(msg.from_user.id, msg.from_user.username)
        await msg.answer(f"✅ Active round canceled & refunded.\n💰 Balance: {user['balance']} credits")
    else:
        await msg.answer("ℹ️ No active round to cancel.")

async def _ensure_no_conflict_round(cb: CallbackQuery) -> bool:
    active = await db.get_active_round(cb.from_user.id)
    if not active:
        return True
    if active["game"] == "blackjack":
        await cb.answer("You already have an active Blackjack round.", show_alert=True)
        return False
    # Legacy/other game -> auto cancel & refund
    await _cancel_active_round(cb.from_user.id, refund=True)
    return True

# ====================================================================================
# Blackjack Helpers
# ====================================================================================

def _overall_flag(flags: Set[str]) -> str:
    if "win" in flags and "loss" not in flags:
        return "win"
    if "loss" in flags and "win" not in flags:
        return "loss"
    if flags == {"push"}:
        return "push"
    return "mixed"

async def _save_state(user_id: int, state_obj: blackjack.BlackjackState):
    await db.update_active_round(user_id, state_obj.to_json())

async def _resolve_and_display(cb: CallbackQuery, state_obj: blackjack.BlackjackState):
    eval_res = state_obj.evaluate()
    total_delta = sum(p for (_t, p, _m) in eval_res["results"])
    flags = {t for (t, _p, _m) in eval_res["results"]}
    overall = _overall_flag(flags)
    await db.resolve_active_round(cb.from_user.id, overall, total_delta)
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    final_txt = blackjack.format_final_results(state_obj, eval_res) + f"\n💰 <b>Balance:</b> {user['balance']} credits"
    await cb.message.edit_text(
        final_txt,
        reply_markup=build_blackjack_result_kb(state_obj.state["original_bet"], user["balance"]),
        parse_mode=ParseMode.HTML
    )

async def _bj_reveal_and_finish_round(cb: CallbackQuery, state_obj: blackjack.BlackjackState):
    state_obj.reveal_dealer()
    await _save_state(cb.from_user.id, state_obj)
    inter = blackjack.format_state_for_display(state_obj, show_dealer_full=True, highlight_current=False)
    inter += "\n\n👀 Dealer reveals the hole card..."
    await cb.message.edit_text(inter, parse_mode=ParseMode.HTML)
    await cb.answer()
    await asyncio.sleep(0.8)

    while state_obj.dealer_play_step():
        await _save_state(cb.from_user.id, state_obj)
        anim = blackjack.format_state_for_display(state_obj, show_dealer_full=True, highlight_current=False)
        anim += "\n\n🀫 Dealer draws..."
        await cb.message.edit_text(anim, parse_mode=ParseMode.HTML)
        await asyncio.sleep(0.7)

    await _resolve_and_display(cb, state_obj)

async def _blackjack_start(cb: CallbackQuery, bet: int):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    if bet < settings.min_bet or bet > settings.max_bet:
        return await cb.answer("Bet out of range.", show_alert=True)
    if bet > user["balance"]:
        return await cb.answer("Not enough balance.", show_alert=True)

    state_obj = blackjack.BlackjackState(bet)
    if not await db.start_active_round(cb.from_user.id, "blackjack", bet, state_obj.to_json()):
        return await cb.answer("Failed to start round (maybe existing round).", show_alert=True)

    player_hand = state_obj.state["player_hands"][0]
    dealer = state_obj.state["dealer"]
    if state_obj.is_blackjack(player_hand) or state_obj.is_blackjack(dealer):
        await _bj_reveal_and_finish_round(cb, state_obj)
        return

    text = blackjack.format_state_for_display(state_obj, show_dealer_full=False)
    await cb.message.edit_text(
        text,
        reply_markup=build_blackjack_actions_kb(
            can_double=state_obj.can_double(),
            can_split=state_obj.can_split()
        ),
        parse_mode=ParseMode.HTML
    )
    await cb.answer("Blackjack started!")

# ====================================================================================
# Blackjack Handlers
# ====================================================================================

@router.callback_query(F.data == "game:blackjack")
async def blackjack_entry(cb: CallbackQuery):
    if not await _ensure_no_conflict_round(cb):
        return
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    if user["balance"] < settings.min_bet:
        await cb.message.edit_text(
            f"❌ Not enough balance (min {settings.min_bet})",
            reply_markup=back_menu_kb(),
            parse_mode=ParseMode.HTML
        )
        return await cb.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💵 Bet {settings.min_bet}", callback_data=f"blackjack:bet:{settings.min_bet}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="nav:menu")]
    ])
    await cb.message.edit_text(
        f"🃏 <b>Blackjack</b>\n\n💰 Balance: {user['balance']} credits\n\nSelect your bet:",
        reply_markup=kb,
        parse_mode=ParseMode.HTML
    )
    await cb.answer()

@router.callback_query(F.data.func(lambda d: d.startswith("blackjack:bet:")))
async def blackjack_place_bet(cb: CallbackQuery):
    if not await _ensure_no_conflict_round(cb):
        return
    try:
        bet = int(cb.data.split(":")[-1])
    except ValueError:
        return await cb.answer("Bad bet.", show_alert=True)
    await _blackjack_start(cb, bet)

@router.callback_query(F.data.func(lambda d: d.startswith("blackjack:same:")))
async def blackjack_same(cb: CallbackQuery):
    if not await _ensure_no_conflict_round(cb):
        return
    try:
        bet = int(cb.data.split(":")[-1])
    except ValueError:
        return await cb.answer("Bad bet.", show_alert=True)
    await _blackjack_start(cb, bet)

@router.callback_query(F.data == "blackjack:hit")
async def blackjack_hit(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "blackjack":
        return await cb.answer("No active Blackjack round.", show_alert=True)
    state_obj = blackjack.BlackjackState.from_json(active["state_json"])
    hand = state_obj.current_hand()

    hand.append(state_obj.draw())
    await _save_state(cb.from_user.id, state_obj)

    text = blackjack.format_state_for_display(state_obj, show_dealer_full=False)
    await cb.message.edit_text(
        text,
        reply_markup=build_blackjack_actions_kb(
            can_double=state_obj.can_double(),
            can_split=state_obj.can_split()
        ),
        parse_mode=ParseMode.HTML
    )
    await cb.answer()

    from games.blackjack import calculate_hand_value
    if calculate_hand_value(hand) > 21:
        state_obj.state["current_hand"] += 1
        await _save_state(cb.from_user.id, state_obj)
        if state_obj.state["current_hand"] < len(state_obj.state["player_hands"]):
            nxt = blackjack.format_state_for_display(state_obj, show_dealer_full=False) + "\n\n💥 Hand busted. Next hand."
            await cb.message.edit_text(
                nxt,
                reply_markup=build_blackjack_actions_kb(
                    can_double=state_obj.can_double(),
                    can_split=state_obj.can_split()
                ),
                parse_mode=ParseMode.HTML
            )
        else:
            await _bj_reveal_and_finish_round(cb, state_obj)

@router.callback_query(F.data == "blackjack:stand")
async def blackjack_stand(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "blackjack":
        return await cb.answer("No active Blackjack round.", show_alert=True)
    state_obj = blackjack.BlackjackState.from_json(active["state_json"])
    state_obj.state["current_hand"] += 1
    await _save_state(cb.from_user.id, state_obj)

    if state_obj.state["current_hand"] < len(state_obj.state["player_hands"]):
        text = blackjack.format_state_for_display(state_obj, show_dealer_full=False)
        await cb.message.edit_text(
            text,
            reply_markup=build_blackjack_actions_kb(
                can_double=state_obj.can_double(),
                can_split=state_obj.can_split()
            ),
            parse_mode=ParseMode.HTML
        )
        return await cb.answer("Next hand.")
    await _bj_reveal_and_finish_round(cb, state_obj)

@router.callback_query(F.data == "blackjack:double")
async def blackjack_double(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "blackjack":
        return await cb.answer("No active Blackjack round.", show_alert=True)
    state_obj = blackjack.BlackjackState.from_json(active["state_json"])
    ci = state_obj.state["current_hand"]
    hand = state_obj.current_hand()
    if len(hand) != 2:
        return await cb.answer("Double only on first two cards.", show_alert=True)
    bet = state_obj.state["bets"][ci]
    state_obj.state["bets"][ci] = bet * 2
    state_obj.state["doubled"][ci] = True
    hand.append(state_obj.draw())
    await _save_state(cb.from_user.id, state_obj)
    state_obj.state["current_hand"] += 1
    await _save_state(cb.from_user.id, state_obj)

    if state_obj.state["current_hand"] < len(state_obj.state["player_hands"]):
        txt = blackjack.format_state_for_display(state_obj, show_dealer_full=False) + "\n\n💰 Doubled. Next hand."
        await cb.message.edit_text(
            txt,
            reply_markup=build_blackjack_actions_kb(
                can_double=state_obj.can_double(),
                can_split=state_obj.can_split()
            ),
            parse_mode=ParseMode.HTML
        )
        return await cb.answer("Doubled.")
    await _bj_reveal_and_finish_round(cb, state_obj)

@router.callback_query(F.data == "blackjack:split")
async def blackjack_split(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "blackjack":
        return await cb.answer("No active Blackjack round.", show_alert=True)
    state_obj = blackjack.BlackjackState.from_json(active["state_json"])
    if not state_obj.can_split():
        return await cb.answer("Cannot split.", show_alert=True)
    idx = state_obj.state["current_hand"]
    hand = state_obj.current_hand()
    c1, c2 = hand
    new1 = [c1, state_obj.draw()]
    new2 = [c2, state_obj.draw()]
    state_obj.state["player_hands"][idx] = new1
    state_obj.state["player_hands"].insert(idx + 1, new2)
    bet = state_obj.state["bets"][idx]
    state_obj.state["bets"].insert(idx + 1, bet)
    state_obj.state["doubled"].insert(idx + 1, False)
    state_obj.state["surrendered"].insert(idx + 1, False)
    state_obj.state["split_count"] = state_obj.state.get("split_count", 0) + 1
    await _save_state(cb.from_user.id, state_obj)

    txt = blackjack.format_state_for_display(state_obj, show_dealer_full=False) + "\n\n🔀 Split performed."
    await cb.message.edit_text(
        txt,
        reply_markup=build_blackjack_actions_kb(
            can_double=state_obj.can_double(),
            can_split=state_obj.can_split()
        ),
        parse_mode=ParseMode.HTML
    )
    await cb.answer("Split done.")

@router.callback_query(F.data == "blackjack:surrender")
async def blackjack_surrender(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "blackjack":
        return await cb.answer("No active round.", show_alert=True)
    state_obj = blackjack.BlackjackState.from_json(active["state_json"])
    ci = state_obj.state["current_hand"]
    while len(state_obj.state["surrendered"]) <= ci:
        state_obj.state["surrendered"].append(False)
    state_obj.state["surrendered"][ci] = True
    state_obj.state["current_hand"] += 1
    await _save_state(cb.from_user.id, state_obj)

    if state_obj.state["current_hand"] < len(state_obj.state["player_hands"]):
        txt = blackjack.format_state_for_display(state_obj, show_dealer_full=False) + "\n\n⚠️ Hand surrendered. Next hand."
        await cb.message.edit_text(
            txt,
            reply_markup=build_blackjack_actions_kb(
                can_double=state_obj.can_double(),
                can_split=state_obj.can_split()
            ),
            parse_mode=ParseMode.HTML
        )
        return await cb.answer("Surrendered.")
    await _bj_reveal_and_finish_round(cb, state_obj)

# ====================================================================================
# Roulette Placeholder
# ====================================================================================

@router.callback_query(F.data == "game:roulette")
async def game_roulette(cb: CallbackQuery):
    await cb.message.edit_text(
        "🎡 Roulette interface is being built. Stay tuned!",
        reply_markup=back_menu_kb(),
        parse_mode=ParseMode.HTML
    )
    await cb.answer()

# ====================================================================================
# Entrypoint
# ====================================================================================

async def main():
    await db.init()
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())