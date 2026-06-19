import enum
from dataclasses import asdict, dataclass


class AssistantType(str, enum.Enum):
    maintenance = "maintenance"
    quality = "quality"
    sop = "sop"
    material = "material"


@dataclass(frozen=True)
class AssistantPreset:
    assistant_type: AssistantType
    display_name: str
    description: str
    system_prompt: str
    default_top_k: int
    default_rerank_top_n: int
    default_use_rerank: bool
    default_auto_metadata_filter: bool
    default_metadata_filter: dict
    answer_format: list[str]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["assistant_type"] = self.assistant_type.value
        return data


PRESETS: dict[AssistantType, AssistantPreset] = {
    AssistantType.maintenance: AssistantPreset(
        assistant_type=AssistantType.maintenance,
        display_name="维修助手",
        description="面向设备故障排查、维修步骤和安全注意事项。",
        system_prompt=(
            "你是 CoreKB 维修助手。只能依据检索到的资料回答，必须给出引用来源。"
            "资料不足时必须明确说“当前资料中未找到足够依据”。"
            "不得编造故障原因、维修步骤、参数或备件信息。回答时区分：已有资料明确说明、根据资料可推断、资料不足无法判断。"
            "优先回答故障代码含义、可能原因、检查步骤、处理方法、安全注意。"
            "涉及停机、断电、拆机时必须提示安全确认。没有对应设备型号或故障码时不得泛化回答。"
        ),
        default_top_k=5,
        default_rerank_top_n=20,
        default_use_rerank=True,
        default_auto_metadata_filter=True,
        default_metadata_filter={"category": "maintenance"},
        answer_format=["故障代码含义", "可能原因", "检查步骤", "处理方法", "安全注意", "引用来源"],
    ),
    AssistantType.quality: AssistantPreset(
        assistant_type=AssistantType.quality,
        display_name="质量助手",
        description="面向检验标准、判定规则和不合格处理。",
        system_prompt=(
            "你是 CoreKB 质量助手。只能依据检索到的资料回答，必须给出引用来源。"
            "资料不足时必须明确说“当前资料中未找到足够依据”。"
            "不得编造检验标准、判定规则、不合格处理方式或版本信息。回答时区分：已有资料明确说明、根据资料可推断、资料不足无法判断。"
            "必须优先给出判定标准和依据，其次给出检验方法和不合格处理。"
            "不确定时提示需要确认最新版质量文件。"
        ),
        default_top_k=5,
        default_rerank_top_n=15,
        default_use_rerank=True,
        default_auto_metadata_filter=True,
        default_metadata_filter={"category": "quality"},
        answer_format=["判定标准", "检验方法", "不合格处理", "版本/依据提醒", "引用来源"],
    ),
    AssistantType.sop: AssistantPreset(
        assistant_type=AssistantType.sop,
        display_name="SOP 助手",
        description="面向工序步骤、关键参数和作业注意事项。",
        system_prompt=(
            "你是 CoreKB SOP 助手。只能依据检索到的资料回答，必须给出引用来源。"
            "资料不足时必须明确说“当前资料中未找到足够依据”。"
            "不得编造步骤、工艺参数、设备设定或安全要求。回答时区分：已有资料明确说明、根据资料可推断、资料不足无法判断。"
            "必须按步骤回答，列出工序名称、操作步骤、关键参数和注意事项。"
            "不得省略安全注意。"
        ),
        default_top_k=5,
        default_rerank_top_n=15,
        default_use_rerank=True,
        default_auto_metadata_filter=True,
        default_metadata_filter={"category": "sop"},
        answer_format=["工序名称", "操作步骤", "关键参数", "注意事项", "安全注意", "引用来源"],
    ),
    AssistantType.material: AssistantPreset(
        assistant_type=AssistantType.material,
        display_name="物料 / 参数助手",
        description="面向物料编码、产品型号、规格参数和替代料查询。",
        system_prompt=(
            "你是 CoreKB 物料 / 参数助手。只能依据检索到的资料回答，必须给出引用来源。"
            "资料不足时必须明确说“当前资料中未找到足够依据”。"
            "不得编造规格参数、供应商、替代料或相似型号关系。回答时区分：已有资料明确说明、根据资料可推断、资料不足无法判断。"
            "必须优先给出物料编码、产品型号、规格参数、电气参数、通信协议、供应商和替代料。"
            "对替代料必须明确资料是否支持替代，不得凭相似型号推断替代关系。"
        ),
        default_top_k=5,
        default_rerank_top_n=20,
        default_use_rerank=True,
        default_auto_metadata_filter=True,
        default_metadata_filter={"category": "material"},
        answer_format=["物料编码 / 产品型号", "关键规格", "电气参数 / 通信协议 / 供应商 / 替代料", "引用来源"],
    ),
}


def get_assistant_preset(assistant_type: str) -> AssistantPreset:
    try:
        return PRESETS[AssistantType(assistant_type)]
    except ValueError as exc:
        raise KeyError(f"Unknown assistant type: {assistant_type}") from exc


def list_assistant_presets() -> list[AssistantPreset]:
    return list(PRESETS.values())
