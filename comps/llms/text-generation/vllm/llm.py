# Copyright (c) 2024 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

from fastapi.responses import StreamingResponse
from langchain_community.llms import VLLMOpenAI

from comps import GeneratedDoc, LLMParamsDoc, ServiceType, opea_microservices, opea_telemetry, register_microservice


@opea_telemetry
def post_process_text(text: str):
    if text == " ":
        return "data: @#$\n\n"
    if text == "\n":
        return "data: <br/>\n\n"
    if text.isspace():
        return None
    new_text = text.replace(" ", "@#$")
    return f"data: {new_text}\n\n"


@register_microservice(
    name="opea_service@llm_vllm",
    service_type=ServiceType.LLM,
    endpoint="/v1/chat/completions",
    host="0.0.0.0",
    port=9000,
)
@opea_telemetry
def llm_generate(input: LLMParamsDoc):
    llm_endpoint = os.getenv("vLLM_LLM_ENDPOINT", "http://localhost:8080")
    llm = VLLMOpenAI(
        openai_api_key="EMPTY",
        endpoint_url=llm_endpoint + "/v1",
        max_tokens=input.max_new_tokens,
        model_name=os.getenv("LLM_MODEL_ID", "meta-llama/Meta-Llama-3-8B-Instruct"),
        top_p=input.top_p,
        temperature=input.temperature,
        presence_penalty=input.repetition_penalty,
        streaming=input.streaming,
    )

    if input.streaming:

        def stream_generator():
            chat_response = ""
            for text in llm.stream(input.query):
                chat_response += text
                processed_text = post_process_text(text)
                if text and processed_text:
                    if "</s>" in text:
                        res = text.split("</s>")[0]
                        if res != "":
                            yield res
                        break
                    yield processed_text
            print(f"[llm - chat_stream] stream response: {chat_response}")
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    else:
        response = llm.invoke(input.query)
        return GeneratedDoc(text=response, prompt=input.query)


if __name__ == "__main__":
    opea_microservices["opea_service@llm_vllm"].start()
