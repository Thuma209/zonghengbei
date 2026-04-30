from static.facilities import FACILITY_SPECS

def apply(state, build_orders):
    for order in build_orders:
        if order.facility in ("land_fort", "coastal_fort"):
            tile = next((t for t in state.tiles if t.code == order.location), None)
            if not tile:
                state.temp["logs"].append(f"建造失败: 地块 {order.location} 不存在")
                continue
            if order.facility == "coastal_fort" and not tile.is_coastal:
                state.temp["logs"].append(f"建造失败: 海岸要塞只能建于沿海地块 ({order.location})")
                continue
            current = tile.land_fort_level if order.facility == "land_fort" else tile.coastal_fort_level
            if order.level <= current:
                state.temp["logs"].append(f"建造失败: 要塞等级必须大于当前等级")
                continue
            if order.level > 5:
                state.temp["logs"].append(f"建造失败: 要塞等级最高5级")
                continue
            base_cost = 4000 if order.facility == "land_fort" else 5000
            cost = base_cost + (order.level - 1) * 1000  # 要塞按单座计费，quantity 忽略
            if state.temp["civ_ic"] >= cost:
                state.temp["civ_ic"] -= cost
                # 直接生效
                if order.facility == "land_fort":
                    tile.land_fort_level = order.level
                else:
                    tile.coastal_fort_level = order.level
                state.temp["logs"].append(f"建造完成: {order.facility} Lv.{order.level} 于 {order.location}")
            else:
                state.temp["logs"].append(f"建造失败: 民用IC不足 (需要 {cost:.0f}，剩余 {state.temp['civ_ic']:.0f})")
        else:
            spec = FACILITY_SPECS.get(order.facility)
            if not spec:
                state.temp["logs"].append(f"建造失败: 未知设施 {order.facility}")
                continue
            if order.facility == "dockyard":
                dock_tile = next((t for t in state.tiles if t.code == order.location), None)
                if not dock_tile or not dock_tile.is_coastal:
                    state.temp["logs"].append(f"建造失败: 船坞只能建于沿海地块 ({order.location})")
                    continue
            cost = spec.build_cost * order.quantity
            if state.temp["civ_ic"] >= cost:
                state.temp["civ_ic"] -= cost
                # 直接生效：更新地块和国家设施总数
                tile = next((t for t in state.tiles if t.code == order.location), None)
                if tile:
                    tile.factories[order.facility] = tile.factories.get(order.facility, 0) + order.quantity
                state.facilities[order.facility] = state.facilities.get(order.facility, 0) + order.quantity
                state.temp["logs"].append(f"建造完成: {order.quantity} x {order.facility} 于 {order.location}")
            else:
                state.temp["logs"].append(f"建造失败: 民用IC不足 (需要 {cost:.0f}，剩余 {state.temp['civ_ic']:.0f})")