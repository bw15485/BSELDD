
from BSE2_msg_classes import Assignment, Order, Exch_msg


##################--Traders below here--#############


# Trader superclass
# all Traders have a trader id, bank balance, blotter, and list of orders to execute
class Trader:

        def __init__(self, ttype, tid, balance, time):
                self.ttype = ttype      # what type / strategy this trader is
                self.tid = tid          # trader unique ID code
                self.balance = balance  # money in the bank
                self.blotter = []       # record of trades executed
                self.orders = []        # customer orders currently being worked
                self.max_cust_orders = 1        # maximum number of distinct customer orders allowed at any one time.
                self.quotes = []        # distinct quotes currently live on the LOB
                self.max_quotes = 1     # maximum number of distinct quotes allowed on LOB
                self.willing = 1        # used in ZIP etc
                self.able = 1           # used in ZIP etc
                self.birthtime = time   # used when calculating age of a trader/strategy
                self.profitpertime = 0  # profit per unit time
                self.n_trades = 0       # how many trades has this trader done?
                self.lastquote = None   # record of what its most recent quote was/is (incl price)


        def __str__(self):
                blotterstring = ''
                for b in self.blotter :
                        blotterstring = blotterstring + '[[%s], %s]' % (str(b[0]), b[1])
                return '[TID=%s type=%s balance=%s blotter=%s orders=%s n_trades=%s profitpertime=%s]' \
                       % (self.tid, self.ttype, self.balance, blotterstring, self.orders, self.n_trades, self.profitpertime)


        def add_cust_order(self, order, verbose):
                # add a customer order to trader's records
                # currently LAZY: keeps to within max_cust_orders by appending new order and deleting head self.orders
                if len(self.quotes) > 0:
                    # this trader has a live quote on the LOB, from a previous customer order
                    # need response to signal cancellation/withdrawal of that quote
                    response = 'LOB_Cancel'
                else:
                    response = 'Proceed'
                if len(self.orders) >= self.max_cust_orders: #currently max_cust_orders a trader can hold is 1
                        self.orders = self.orders[1:]
                self.orders.append(order)
                if verbose: print('add_order < response=%s self.orders=%s' % (response, str(self.orders)))
                return response


        # delete a customer order from trader's list of orders being worked
        def del_cust_order(self, cust_order_id, verbose):
                if verbose:
                        print('>del_cust_order: Cust_orderID=%s; self.orders=' % cust_order_id)
                        for o in self.orders: print('%s ' % str(o))

                cust_orders = []
                for co in self.orders:
                        if co.assignmentid != cust_order_id: cust_orders.append(co)

                self.orders = cust_orders


        # revise a customer order: used after a PARTial fill on the exchange
        def revise_cust_order(self, cust_order_id, revised_order, verbose):
                if verbose:
                        print('>revise_cust_order: Cust_orderID=%s; revised_order=%s, self.orders=' % (cust_order_id, revised_order))
                        for o in self.orders: print('%s ' % str(o))

                cust_orders = []
                for co in self.orders:
                        if co.assignmentid != cust_order_id: cust_orders.append(co)
                        else:
                                revised_assignment = co
                                revised_assignment.qty = revised_order.qty
                                cust_orders.append(revised_assignment)

                self.orders = cust_orders

                if verbose:
                        print('<revise_cust_order: Cust_orderID=%s; revised_order=%s, self.orders=' % (cust_order_id, revised_order))
                        for o in self.orders: print('%s ' % str(o))


        # delete an order/quote from the trader's list of its orders live on the exchange
        def del_exch_order(self, oid, verbose):
                if verbose:
                        print('>del_exch_order: OID:%d; self.quotes=' % oid)
                        for q in self.quotes: print('%s ' % str(q))

                exch_orders = []
                for eo in self.quotes:
                        if eo.orderid != oid: exch_orders.append(eo)

                self.quotes= exch_orders


        def bookkeep(self, msg, time, verbose):
                # bookkeep(): trader book-keeping in response to message from the exchange
                # update records of what orders are still being worked, account balance, etc.
                # trader's blotter is a simple sequential record of each exchange messages received, and the trader's balance after bookeeping that msh

                if verbose: print('>bookkeep msg=%s bal=%d' % (msg, self.balance))

                profit = 0

                if msg.event == "CAN":
                        # order was cancelled at the exchange
                        # so delete the order from the trader's records of what quotes it has live on the exchange
                        if verbose:
                                print(">CANcellation: msg=%s quotes=" % str(msg))
                                for q in self.quotes: print("%s" % str(q))

                        newquotes = []
                        for q in self.quotes:
                                if q.orderid != msg.oid:
                                        newquotes.append(q)
                        self.quotes = newquotes

                        if verbose:
                                print("<CANcellation: quotes=")
                                for q in self.quotes: print("%s" % str(q))


                # an individual order of some types (e.g. MKT) can fill via transactions at different prices
                # so the message that comes back from the exchange has transaction data in a list: will often be length=1

                if msg.event == "FILL" or msg.event == "PART":

                        for trans in msg.trns:
                                transactionprice = trans["Price"]
                                qty = trans["Qty"]

                                # find this LOB order in the trader's list of quotes sent to exchange
                                exch_order = None
                                for ord in self.quotes:
                                        if ord.orderid == msg.oid:
                                                exch_order = ord
                                        break
                                if exch_order == None:
                                        s = 'FAIL: bookkeep() cant find order (msg.oid=%d) orders=' % msg.oid
                                        for ord in self.quotes: s = s + str(ord)
                                        sys.exit(s)

                                limitprice = exch_order.price

                                if exch_order.otype == 'Bid':
                                        profit = (limitprice - transactionprice) * qty
                                else:
                                        profit = (transactionprice - limitprice) * qty

                                self.balance += profit
                                self.n_trades += 1
                                age = time - self.birthtime
                                self.profitpertime = self.balance / age

                                if verbose: print('Price=%d Limit=%d Q=%d Profit=%d N_trades=%d Age=%f Balance=%d' %
                                                  (transactionprice, limitprice, qty, profit, self.n_trades, age, self.balance))

                                if profit < 0:
                                        print self.tid
                                        print self.ttype
                                        print profit
                                        print exch_order
                                        #sys.exit('Exit: Negative profit')

                        if verbose: print('%s: profit=%d bal=%d profit/time=%f' %
                                  (self.tid, profit, self.balance, self.profitpertime))

                        # by the time we get to here, exch_order is instantiated
                        cust_order_id = exch_order.myref

                        if msg.event == "FILL":
                                # this order has completed in full, so it thereby completes the corresponding customer order
                                # so delete both the customer order from trader's record of those
                                # and the order has already been deleted from the exchange's records, so also needs to be deleted from trader's records of orders held at exchange
                                cust_order_id = exch_order.myref
                                if verbose: print('>bookkeep() deleting customer order ID=%s' % cust_order_id)
                                self.del_cust_order(cust_order_id, verbose)  # delete this customer order
                                if verbose: print(">bookkeep() deleting OID:%d from trader's exchange-order records" % exch_order.orderid)
                                self.del_exch_order(exch_order.orderid, verbose) # delete the exchange-order from trader's records

                        elif msg.event == "PART":
                                # the customer order is still live, but its quantity needs updating
                                if verbose: print('>bookkeep() PART-filled order updating qty on customer order ID=%s' % cust_order_id)
                                self.revise_cust_order(cust_order_id, msg.revo, verbose)  # delete this customer order

                                if exch_order.ostyle == "IOC":
                                        # a partially filled IOC has the non-filled portion cancelled at the exchange,
                                        # so the trader's order records need to be updated accordingly
                                        if verbose: print(">bookkeep() PART-filled IOC cancels remainder: deleting OID:%d from trader's exchange-order records" % exch_order.orderid)
                                        self.del_exch_order(exch_order.orderid, verbose)  # delete the exchange-order from trader's records

                self.blotter.append([msg, self.balance])  # add trade record to trader's blotter


        # specify how trader responds to events in the market
        # this is a null action, expect it to be overloaded by specific algos
        def respond(self, time, lob, trade, verbose):
                return None


        # specify how trader mutates its parameter values
        # this is a null action, expect it to be overloaded by specific algos
        def mutate(self, time, lob, trade, verbose):
                return None


# Trader subclass Giveaway
# even dumber than a ZI-U: just give the deal away
# (but never makes a loss)
class Trader_Giveaway(Trader):

        def getorder(self, time, countdown, lob, verbose):

                if verbose: print('GVWY getorder:')

                if len(self.orders) < 1:
                        order = None
                else:
                        quoteprice = self.orders[0].price
                        order = Order(self.tid,
                                    self.orders[0].otype,
                                    self.orders[0].ostyle,
                                    quoteprice,
                                    self.orders[0].qty,
                                    time, None, -1)
                        self.lastquote=order
                return order



# Trader subclass ZI-C
# After Gode & Sunder 1993
class Trader_ZIC(Trader):

        def getorder(self, time, countdown, lob, verbose):

                if verbose: print('ZIC getorder:')

                if len(self.orders) < 1:
                        # no orders: return NULL
                        order = None
                else:
                        minprice = lob['bids']['worstp']
                        maxprice = lob['asks']['worstp']

                        limit = self.orders[0].price
                        otype = self.orders[0].atype
                        ostyle = self.orders[0].astyle
                        if otype == 'Bid':
                                oprice = random.randint(minprice, limit)
                        else:
                                oprice = random.randint(limit, maxprice)
                                # NB should check it == 'Ask' and barf if not
                        order = Order(self.tid, otype, ostyle, oprice, self.orders[0].qty, time, None, -1)
                        self.lastquote = order
                return order



# Trader subclass Shaver
# shaves a penny off the best price
class Trader_Shaver(Trader):

        def getorder(self, time, countdown, lob, verbose):

                if verbose: print("SHVR getorder:")

                if len(self.orders) < 1:
                        order = None
                else:
                        if verbose: print(" self.orders[0]=%s" % str(self.orders[0]))
                        limitprice = self.orders[0].price
                        otype = self.orders[0].atype
                        ostyle = self.orders[0].astyle
                        if otype == 'Bid':
                                if lob['bids']['n'] > 0:
                                        quoteprice = lob['bids']['bestp'] + 1
                                        if quoteprice > limitprice :
                                                quoteprice = limitprice
                                else:
                                        quoteprice = lob['bids']['worstp']
                        else:
                                if lob['asks']['n'] > 0:
                                        quoteprice = lob['asks']['bestp'] - 1
                                        if quoteprice < limitprice:
                                                quoteprice = limitprice
                                else:
                                        quoteprice = lob['asks']['worstp']
                        order = Order(self.tid, otype, ostyle, quoteprice, self.orders[0].qty, time, None, -1)
                        self.lastquote = order
                return order



# Trader subclass Imbalance-sensitive Shaver
# shaves X off the best price, where X depends on supply/demand imbalance
class Trader_ISHV(Trader):


        def getorder(self, time, countdown, lob, verbose):

                if verbose: print("ISHV getorder:")

                shave_c = 2 # c in the y=mx+c linear mapping from imbalance to shave amount
                shave_m = 1 # m in the y=mx+c

                if len(self.orders) < 1:
                        order = None
                else:
                        if verbose: print(" self.orders[0]=%s" % str(self.orders[0]))
                        limitprice = self.orders[0].price
                        otype = self.orders[0].atype
                        ostyle = self.orders[0].astyle

                        microp = lob['microprice']
                        midp = lob['midprice']

                        if microp != None and midp != None:
                                imbalance = microp - midp
                        else: imbalance = 0 # if imbalance is undefined, proceed as if it is equal to zero


                        if otype == 'Bid':

                                # quantity sensitivity
                                if imbalance < 0 : shaving = 1 # imbalance in favour of buyers, so shave slowly
                                else: shaving = shave_c + (shave_m * int(imbalance*100)/100) # shave ever larger amounts

                                print('t:%f, ISHV (Bid) imbalance=%s shaving=%s' % (time, imbalance, shaving))

                                if len(lob['bids']['lob']) > 0:
                                        quoteprice = lob['bids']['bestp'] + shaving
                                        if quoteprice > limitprice :
                                                quoteprice = limitprice
                                else:
                                        quoteprice = 1 #KLUDGE -- come back to fix todo
                        else:
                                # quantity sensitivity
                                if imbalance > 0 : shaving = 1
                                else: shaving = shave_c - (shave_m * int(imbalance*100)/100)

                                print('t:%f, ISHV (Ask) imbalance=%s shaving=%s' % (time, imbalance, shaving))

                                if len(lob['asks']['lob']) > 0:
                                        quoteprice = lob['asks']['bestp'] - shaving
                                        if quoteprice < limitprice :
                                                quoteprice = limitprice
                                else:
                                        quoteprice = 200 #KLUDGE -- come back to fix todo

                        order = Order(self.tid, otype, ostyle, quoteprice, self.orders[0].qty, time, None, verbose)
                        self.lastquote = order
                return order



# Trader subclass Sniper
# Based on Shaver, inspired by Kaplan
# "lurks" until time remaining < threshold% of the trading session
# then gets increasing aggressive, increasing "shave thickness" as time runs out
class Trader_Sniper(Trader):

        def getorder(self, time, countdown, lob, verbose):

                if verbose: print('SNPR getorder: self.orders[0]=%s' % str(self.orders[0]))

                lurk_threshold = 0.2
                shavegrowthrate = 3
                shave = int(1.0 / (0.01 + countdown / (shavegrowthrate * lurk_threshold)))
                if (len(self.orders) < 1) or (countdown > lurk_threshold):
                        order = None
                else:
                        limitprice = self.orders[0].price
                        otype = self.orders[0].otype
                        ostyle = self.orders[0].ostyle
                        if otype == 'Bid':
                                if lob['bids']['n'] > 0:
                                        oprice = lob['bids']['bestp'] + shave
                                        if oprice > limitprice:
                                                oprice = limitprice
                                else:
                                        oprice = lob['bids']['worstp']
                        else:
                                if lob['asks']['n'] > 0:
                                        oprice = lob['asks']['bestp'] - shave
                                        if oprice < limitprice:
                                                oprice = limitprice
                                else:
                                        oprice = lob['asks']['worstp']
                        order = Order(self.tid, otype, ostyle, oprice, self.orders[0].qty, time, None, -1)
                        self.lastquote = order
                return order



# Trader subclass ZIP
# After Cliff 1997
class Trader_ZIP(Trader):

        # ZIP init key param-values are those used in Cliff's 1997 original HP Labs tech report
        # NB this implementation keeps separate margin values for buying & selling,
        #    so a single trader can both buy AND sell
        #    -- in the original, traders were either buyers OR sellers

        def __init__(self, ttype, tid, balance, time):
                Trader.__init__(self, ttype, tid, balance, time)
                m_fix = 0.05
                m_var = 0.05
                self.job = None                                 # this is 'Bid' or 'Ask' depending on customer order
                self.active = False                             # gets switched to True while actively working an order
                self.prev_change = 0                            # this was called last_d in Cliff'97
                self.beta = 0.1 + 0.2 * random.random()         # learning rate
                self.momntm = 0.3 * random.random()             # momentum
                self.ca = 0.10                                  # self.ca & .cr were hard-coded in '97 but parameterised later
                self.cr = 0.10
                self.margin = None                              # this was called profit in Cliff'97
                self.margin_buy = -1.0 * (m_fix + m_var * random.random())
                self.margin_sell = m_fix + m_var * random.random()
                self.price = None
                self.limit = None
                # memory of best price & quantity of best bid and ask, on LOB on previous update
                self.prev_best_bid_p = None
                self.prev_best_bid_q = None
                self.prev_best_ask_p = None
                self.prev_best_ask_q = None
                # memory of worst prices from customer orders received so far
                self.worst_bidprice = None
                self.worst_askprice = None


        def __str__(self):
                s = '%s, job=, %s, ' % (self.tid, self.job)
                if self.active == True: s = s +'actv=,T, '
                else: s = s + 'actv=,F, '
                if self.margin == None: s = s + 'mrgn=,N,   '
                else: s = s + 'mrgn=,%5.2f, ' % self.margin
                s = s + 'lmt=,%s, price=,%s, bestbid=,%s,@,%s, bestask=,%s,@,%s, wrstbid=,%s, wrstask=,%s' %\
                    (self.limit, self.price, self.prev_best_bid_q, self.prev_best_bid_p, self.prev_best_ask_q, self.prev_best_ask_p, self.worst_bidprice, self.worst_askprice)
                return(s)


        def getorder(self, time, countdown, lob, verbose):

                if verbose: print('ZIP getorder(): LOB=%s' % lob)

                # random coefficient, multiplier on trader's own estimate of worst possible bid/ask prices
                # currently in arbitrarily chosen range [2, 5]
                worst_coeff = 2 + (3 * random.random())

                if len(self.orders) < 1:
                        self.active = False
                        order = None
                else:
                        self.active = True
                        self.limit = self.orders[0].price
                        self.job = self.orders[0].atype
                        if self.job == 'Bid':
                                # currently a buyer (working a bid order)
                                self.margin = self.margin_buy
                                # what is the worst bid price on the LOB right now?
                                if len(lob['bids']['lob']) > 0 :
                                        # take price of final entry on LOB
                                        worst_bid = lob['bids']['lob'][-1][0]
                                else:
                                        # local pessimistic estimate of the worst bid price (own version of stub quote)
                                        worst_bid = max(1, int(self.limit / worst_coeff))
                                if self.worst_bidprice == None: self.worst_bidprice = worst_bid
                                elif self.worst_bidprice > worst_bid: self.worst_bidprice = worst_bid
                        else:
                                # currently a seller (working a sell order)
                                self.margin = self.margin_sell
                                # what is the worst ask price on the LOB right now?
                                if len(lob['asks']['lob']) > 0 :
                                        # take price of final entry on LOB
                                        worst_ask = lob['asks']['lob'][-1][0]
                                else:
                                        # local pessimistic estimate of the worst ask price (own version of stub quote)
                                        worst_ask = int(self.limit * worst_coeff)
                                if self.worst_askprice == None: self.worst_askprice = worst_ask
                                elif self.worst_askprice < worst_ask: self.worst_askprice = worst_ask

                        quoteprice = int(self.limit * (1 + self.margin))
                        self.price = quoteprice

                        order = Order(self.tid, self.job, "LIM", quoteprice, self.orders[0].qty, time, None, -1)
                        self.lastquote = order

                return order


        # update margin on basis of what happened in market
        def respond(self, time, lob, trade, verbose):
                # ZIP trader responds to market events, altering its margin
                # does this whether it currently has an order to work or not

                def target_up(price):
                        # generate a higher target price by randomly perturbing given price
                        ptrb_abs = self.ca * random.random()  # absolute shift
                        ptrb_rel = price * (1.0 + (self.cr * random.random()))  # relative shift
                        target = int(round(ptrb_rel + ptrb_abs, 0))
                        if target == price: target = price + 1  # enforce minimal difference
                        print('TargetUp: %d %d\n' % (price, target))
                        return(target)


                def target_down(price):
                        # generate a lower target price by randomly perturbing given price
                        ptrb_abs = self.ca * random.random()  # absolute shift
                        ptrb_rel = price * (1.0 - (self.cr * random.random()))  # relative shift
                        target = int(round(ptrb_rel - ptrb_abs, 0))
                        if target == price : target = price -1 # enforce minimal difference
                        print('TargetDn: %d %d\n' % (price,target))
                        return(target)


               #this at the minute just returns the price?
                def microshade(microprice, price):
                        # shade in the direction of the microprice
                        microweight = 0
                        if microprice != None: shaded = ((microweight * microprice) + ((1 - microweight) * price))
                        else: shaded = price
                        print('Microshade: micro=%s price=%s shaded=%s' % (microprice, price, shaded))
                        return(shaded)


                def willing_to_trade(price):
                        # am I willing to trade at this price?
                        willing = False
                        if self.job == 'Bid' and self.active and self.price >= price:
                                willing = True
                        if self.job == 'Ask' and self.active and self.price <= price:
                                willing = True
                        return willing


                def profit_alter(*argv):
                        # this has variable number of parameters
                        # if passed a single numeric value, that's the target price
                        # if passed three numeric values, that's the price, beta (learning rate), and momentum
                        if len(argv) == 1 :
                                price = argv[0]
                                beta = self.beta
                                momntm = self.momntm
                        elif len(argv) == 3 :
                                price = argv[0]
                                beta = argv[1]
                                momntm = argv[2]
                        else:
                                sys.stdout.flush()
                                sys.exit('Fail: ZIP profit_alter given wrong number of parameters')

                        print('profit_alter: price=%s beta=%s momntm=%s' % (price, beta, momntm))
                        oldprice = self.price
                        diff = price - oldprice
                        change = ((1.0 - self.momntm) * (self.beta * diff)) + (self.momntm * self.prev_change)
                        self.prev_change = change
                        newmargin = ((self.price + change) / self.limit) - 1.0

                        if self.job == 'Bid':
                                margin = min(newmargin, 0)
                                self.margin_buy = margin
                                self.margin = margin
                        else :
                                margin = max(0, newmargin)
                                self.margin_sell = margin
                                self.margin = margin

                        # set the price from limit and profit-margin
                        self.price = int(round(self.limit * (1.0 + self.margin), 0))
                        print('old=%d diff=%d change=%d lim=%d price = %d\n' % (oldprice, diff, change, self.limit, self.price))


                if verbose and trade != None: print('respond() [ZIP] time=%s tid=%s, trade=%s LOB[bids]=%s LOB[asks]=%s' %
                                                    (time, self.tid, trade, lob["bids"], lob["asks"]))


                # what, if anything, has happened on the bid LOB?

                if trade != None: print('ZIP respond() trade=%s' % trade)

                bid_improved = False
                bid_hit = False

                if len(lob['bids']['lob']) > 0: lob_best_bid_p = lob['bids']['lob'][0][0]
                else: lob_best_bid_p = None

                lob_best_bid_q = None                   # default assumption

                if lob_best_bid_p != None:
                        # non-empty bid LOB

                        if self.prev_best_bid_p > lob_best_bid_p : best_bid_p_decreased = True
                        else: best_bid_p_decreased = False

                        if (self.prev_best_bid_p == lob_best_bid_p) and (self.prev_best_bid_q > lob_best_bid_q): same_p_smaller_q = True
                        else: same_p_smaller_q = False

                        lob_best_bid_q = lob['bids']['lob'][0][1]

                        if self.prev_best_bid_p < lob_best_bid_p :
                                # best bid has improved
                                # NB doesn't check if the improvement was by self
                                bid_improved = True
                        elif trade != None and (best_bid_p_decreased or same_p_smaller_q) :
                                # there WAS a trade and either...
                                # ... (best bid price has gone DOWN) or (best bid price is same but quantity at that price has gone DOWN)
                                # then assume previous best bid was hit
                                bid_hit = True

                elif self.prev_best_bid_p != None:
                        # the bid LOB is empty now but was not previously: so was it canceled or lifted?
                        if trade !=  None:
                                # a trade has occurred and the previously nonempty ask LOB is now empty
                                # so assume best ask was lifted
                                bid_hit = True
                        else:
                                bid_hit = False

                if verbose: print("LOB[bids]=%s bid_improved=%s bid_hit=%s" % (lob['bids'], bid_improved, bid_hit))


                # what, if anything, has happened on the ask LOB?

                ask_improved = False
                ask_lifted = False

                if len(lob['asks']['lob']) > 0: lob_best_ask_p = lob['asks']['lob'][0][0]
                else: lob_best_ask_p = None

                lob_best_ask_q = None

                if lob_best_ask_p != None:
                        # non-empty ask LOB

                        if self.prev_best_ask_p < lob_best_ask_p: best_ask_p_increased = True
                        else: best_ask_p_increased = False

                        if (self.prev_best_ask_p == lob_best_ask_p) and (self.prev_best_ask_q > lob_best_ask_q): same_p_smaller_q = True
                        else: same_p_smaller_q = False

                        lob_best_ask_q = lob['asks']['lob'][0][1]
                        if self.prev_best_ask_p > lob_best_ask_p :
                                # best ask has improved -- NB doesn't check if the improvement was by self
                                ask_improved = True
                        elif trade != None and (best_ask_p_increased or same_p_smaller_q):
                                # trade happened and best ask price has got worse, or stayed same but quantity reduced -- assume previous best ask was lifted
                                ask_lifted = True

                elif self.prev_best_ask_p != None:
                        # the ask LOB is empty now but was not previously: so was it canceled or lifted?
                        if trade !=  None:
                                # a trade has occurred and the previously nonempty ask LOB is now empty
                                # so assume best ask was lifted
                                ask_lifted = True
                        else:
                                ask_lifted = False


                if verbose: print("LOB[asks]=%s ask_improved=%s ask_lifted=%s" % (lob['asks'], ask_improved, ask_lifted))


                if verbose and (bid_improved or bid_hit or ask_improved or ask_lifted):
                        print('ZIP respond() B_improved=%s; B_hit=%s A_improved=%s, A_lifted=%s' % (bid_improved, bid_hit, ask_improved, ask_lifted))
                        print('Trade=%s\n' % trade)


                # we want to know: did a deal just happen?
                # if not, did the most recent bid


                deal = bid_hit or ask_lifted


                # previously...
                # when raising margin, tradeprice = trade['price'], targetprice = f(tradeprice) &
                # i.e. target price will be calculated relative to price of most recent transaction
                # and when lowering margin, targetprice = f(best_price_on_counterparty_side_of_LOB) or
                # or if LOB empty then targetprice = f(worst possible counterparty quote) <-- a system constant


                # new in this version:
                # take account of LOB's microprice if it is defined (if not, use trade['price'] as before)

                midp = lob['midprice']
                microp = lob['microprice']

                # KLUDGE for TESTING
                if time > 79: microp = 145

                if microp != None and midp != None :
                        imbalance = microp - midp
                else:
                        imbalance = 0  # uses zero instead of None because a zero imbalance reverts ZIP to original form


                target_price = None # default assumption

                print('self.job=%s' % self.job)

                if self.job == 'Ask':
                        # seller
                        if deal:
                                if verbose: print ('trade',trade)
                                tradeprice = trade['price']  # price of most recent transaction
                                print('tradeprice=%s lob[microprice]=%s' % (tradeprice, lob['microprice']))
                                shadetrade = microshade(lob['microprice'], tradeprice) #shadeprice currently just equals the price
                                refprice = shadetrade

                                if self.price <= tradeprice:
                                        # could sell for more? raise margin
                                        target_price = target_up(refprice)
                                        profit_alter(target_price)
                                elif ask_lifted and self.active and not willing_to_trade(tradeprice):
                                        # previous best ask was hit,
                                        # but this trader wouldn't have got the deal cos price to high,
                                        # and still working a customer order, so reduce margin
                                        target_price = target_down(refprice)
                                        profit_alter(target_price)
                        else:
                                # no deal: aim for a target price higher than best bid
                                print('lob_best_bid_p=%s lob[microprice]=%s' % (lob_best_bid_p, lob['microprice']))
                                refprice = microshade(lob['microprice'], lob_best_bid_p)

                                if ask_improved and self.price > lob_best_bid_p:
                                        if lob_best_bid_p != None:
                                                target_price = target_up(lob_best_bid_p)
                                        else:
                                                if self.worst_askprice != None:
                                                        target_price = self.worst_askprice
                                                        print('worst_askprice = %s' % self.worst_askprice)
                                                        target_price = None #todo: does this stop the price-spikes?
                                                else:   target_price = None
                                                        # target_price = lob['asks']['worstp']  # stub quote
                                        if target_price != None:
                                                print('PA1: tp=%s' % target_price)
                                                profit_alter(target_price)

                if self.job == 'Bid':
                        # buyer
                        if deal:
                                tradeprice = trade['price']
                                shadetrade = microshade(lob['microprice'], tradeprice)
                                refprice = shadetrade

                                if lob['microprice'] != None and lob['midprice'] != None:
                                        delta = lob['microprice'] - lob['midprice']
                                        # refprice = refprice + delta

                                if self.price >= tradeprice :
                                        # could buy for less? raise margin (i.e. cut the price)
                                        target_price = target_down(refprice)
                                        profit_alter(target_price)
                                elif bid_hit and self.active and not willing_to_trade(tradeprice):
                                        # wouldn't have got this deal, and still working a customer order,
                                        # so reduce margin
                                        target_price = target_up(refprice)
                                        profit_alter(target_price)
                        else:
                                # no deal: aim for target price lower than best ask
                                refprice = microshade(lob['microprice'], lob_best_ask_p)
                                if bid_improved and self.price < lob_best_ask_p:
                                        if lob_best_ask_p != None:
                                                target_price = target_down(lob_best_ask_p)
                                        else:
                                                if self.worst_bidprice != None :
                                                        target_price = self.worst_bidprice
                                                        target_price = None
                                                else:   target_price = None
                                                        # target_price = lob['bids']['worstp']  # stub quote
                                        if target_price != None:
                                                print('PA2: tp=%s' % target_price)

                                                profit_alter(target_price)



                print('time,%f,>>>,microprice,%s,>>>,target_price,%s' % (time, lob['microprice'], target_price))

                # remember the best LOB data ready for next response
                self.prev_best_bid_p = lob_best_bid_p
                self.prev_best_bid_q = lob_best_bid_q
                self.prev_best_ask_p = lob_best_ask_p
                self.prev_best_ask_q = lob_best_ask_q



##########################---trader-types have all been defined now--################
