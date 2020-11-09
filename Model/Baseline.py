from config import args
import torch.nn as nn
import torch.nn.functional as F
import torch
from transformers import BertModel
from Layers import GraphConvolution, SentenceMatrixLayer, EncodeLayer, feedforwardLayer, GCN
from Attention import MultiHeadedAttention


class GraphBaseline(nn.Module):
    def __init__(self, in_size=768, bi_hidden_size=300, bi_out_size=1024, gc_size=300, at_size=600,
                 linear_hidden_size=300, out_size=1, head=1, dropout=0.1):
        super(GraphBaseline, self).__init__()
        self.bert = BertModel.from_pretrained(args.bert_model)

        # self.embedding = nn.Embedding(len, in_size, padding_idx=1)
        self.context_embedding = EncodeLayer(in_size=in_size, hidden_size=bi_hidden_size)
        self.c2a = nn.Linear(bi_hidden_size * 2, bi_out_size)

        self.A_matrix = SentenceMatrixLayer(in_size=bi_out_size)
        self.gcn = GCN(bi_hidden_size * 2, gc_size, at_size, dropout)
        # self.gcn2 = GCN(gc_size, gc_size, at_size, dropout)

        self.pre = MultiHeadedAttention(head, at_size, at_size, dropout)

        self.outlinear1 = nn.Linear(in_size, linear_hidden_size)
        self.outlinear2 = nn.Linear(linear_hidden_size, out_size)
        self.dropout_out = nn.Dropout(dropout)

    def forward(self, x, adj, trigger_index, mask):
        # x: [batch, seq_len]
        # adj: [batch, seq_len, seq_len]
        # trigger_index: [batch]
        # mask: [batch, seq_len]
        x = self.bert(x, attention_mask=mask)[0]
        cls, x, _ = x.split([1, x.shape[1] - 2, 1], dim=1)  # [batch, 1, input_size], [batch, seq_len, input_size]

        '''
        x = self.context_embedding(x, mask)  # [batch, seq_len, bi_hidden_size * 2]
        h = torch.tanh(self.c2a(x))  # [batch, seq_len, bi_out_size]

        a = self.A_matrix(h, adj)  # [batch, seq_len, seq_len]

        x = self.gcn(x, a)  # [batch, seq_len, at_size]

        one_hot = F.one_hot(torch.arange(0, trigger_index.max() + 1), x.shape[1]).to(trigger_index.device)
        trigger_index = one_hot[trigger_index].unsqueeze(-1)  # [batch, seq_len, 1]
        trigger_index = trigger_index.expand(-1, -1, x.shape[-1]).bool()  # [batch, seq_len, at_size]
        trigger_index_x = x.masked_select(trigger_index).view(x.shape[0], 1, x.shape[-1])  # [batch, 1, at_size], vector of trigger_index

        x = self.pre(trigger_index_x, x, x, mask)
        '''

        batch, seq_len, embed_dim = x.shape

        diag_matrix = torch.diag(torch.ones(seq_len)).cuda()
        trigger_index = diag_matrix[trigger_index].bool().unsqueeze(-1).expand(-1, -1, embed_dim)
        x = x.masked_select(trigger_index).view(batch, -1)  # [batch, at_size]

        x = self.outlinear1(x)
        x = F.relu(x)
        x= self.dropout_out(x)
        x = self.outlinear2(x)

        return x.squeeze()
